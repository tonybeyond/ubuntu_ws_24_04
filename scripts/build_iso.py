#!/usr/bin/env python3
import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from iso_config import autoinstall, identity, patch_grub, verify_payload

ROOT = Path(__file__).resolve().parent.parent
RELEASE = "https://releases.ubuntu.com/24.04/"
POP_COMMIT = "7898b65c20735057faf0797f8ed056704ca55f0d"
THEME_COMMIT = "4b76ab021d09daa22eb48c7e61928fa13700eaed"
KEYRING = Path("/usr/share/keyrings/ubuntu-archive-keyring.gpg")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": "ubunturiri-ISO/1"})
    temporary = Path(str(path) + ".part")
    try:
        with urllib.request.urlopen(request, timeout=120) as source, temporary.open("wb") as destination:
            if not source.geturl().startswith("https://"):
                raise ValueError("Téléchargement non HTTPS refusé.")
            shutil.copyfileobj(source, destination)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run(arguments, **kwargs):
    return subprocess.run([str(value) for value in arguments], check=True, **kwargs)


def preflight():
    if platform.system() != "Linux" or sys.version_info < (3, 12):
        raise ValueError("Construire dans Ubuntu 24.04 avec Python 3.12 ou ultérieur, pas directement sous macOS.")
    release = platform.freedesktop_os_release()
    if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
        raise ValueError("L’hôte de construction doit être Ubuntu 24.04.")
    required = ["xorriso", "openssl", "gpgv", "dpkg-deb"]
    missing = [name for name in required if not shutil.which(name)]
    if missing or not KEYRING.is_file():
        raise ValueError("Dépendances requises : sudo apt install python3 xorriso openssl gpgv ubuntu-keyring")
    if os.geteuid() == 0:
        raise ValueError("Lancer la construction sans sudo ; seuls les prérequis nécessitent sudo.")
    print("Prérequis de construction vérifiés.")


def select_iso(checksums):
    candidates = []
    for line in checksums.splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(ubuntu-24\.04(?:\.(\d+))?-live-server-amd64\.iso)", line)
        if match:
            candidates.append((int(match[3] or 0), match[2], match[1].lower()))
    if not candidates:
        raise ValueError("Aucune ISO Ubuntu Server 24.04 AMD64 dans le manifeste signé.")
    _, name, digest = max(candidates)
    return name, digest


def official_iso(cache, supplied):
    download(RELEASE + "SHA256SUMS", cache / "SHA256SUMS")
    download(RELEASE + "SHA256SUMS.gpg", cache / "SHA256SUMS.gpg")
    run(["gpgv", "--keyring", KEYRING, cache / "SHA256SUMS.gpg", cache / "SHA256SUMS"])
    name, digest = select_iso((cache / "SHA256SUMS").read_text())
    path = supplied.resolve() if supplied else cache / name
    if supplied and supplied.name != name:
        raise ValueError(f"L’ISO fournie doit être la version courante vérifiée : {name}")
    if not path.is_file():
        if supplied:
            raise ValueError("ISO fournie introuvable.")
        print(f"Téléchargement de {name}.")
        download(RELEASE + name, path)
    if sha256(path) != digest:
        raise ValueError("SHA-256 de l’ISO officielle incorrect ; fichier refusé.")
    print("Signature Ubuntu et SHA-256 de l’ISO vérifiés.")
    return path


def unpack(archive, destination):
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if any(member.isdev() for member in members):
            raise ValueError("Archive contenant des fichiers spéciaux refusée.")
        source.extractall(destination, filter="data")
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("Structure de l’archive inattendue.")
    for path in roots[0].rglob("*"):
        if not path.resolve().is_relative_to(roots[0].resolve()):
            raise ValueError("Lien sortant de l’arborescence source refusé.")
    return roots[0]


def prepare_payload(work, citrix):
    payload = work / "payload"
    payload.mkdir()
    for name in ["iso_config.py", "install-desktop.sh", "session_setup.py", "theme.py", "citrix_mode.py"]:
        shutil.copy2(ROOT / "scripts" / name, payload / name)
    if not citrix.is_file():
        raise ValueError("Fournir le paquet DEB AMD64 officiel de Citrix Workspace avec --citrix-deb.")
    for field, expected in [("Package", "icaclient"), ("Architecture", "amd64")]:
        value = run(["dpkg-deb", "--field", citrix, field], capture_output=True, text=True).stdout.strip()
        if value != expected:
            raise ValueError("Le paquet fourni n’est pas Citrix Workspace AMD64 (icaclient).")
    shutil.copy2(citrix, payload / "icaclient.deb")
    for name, repository, commit in [("pop-shell", "pop-os/shell", POP_COMMIT), ("fedoriri", "tonybeyond/fedoriri", THEME_COMMIT)]:
        archive = work / f"{name}.tar.gz"
        download(f"https://codeload.github.com/{repository}/tar.gz/{commit}", archive)
        extracted = work / f"{name}-source"
        extracted.mkdir()
        source = unpack(archive, extracted)
        if name == "pop-shell":
            metadata = json.loads((source / "metadata.json").read_text())
            if "46" not in metadata["shell-version"]:
                raise ValueError("Pop Shell ne déclare pas GNOME 46 compatible.")
            shutil.copytree(source, payload / "pop-shell")
        else:
            shutil.copytree(source / "desktop/themes", payload / "themes")
            shutil.copy2(source / "LICENSE", payload / "LICENSE-fedoriri")
    download("https://raw.githubusercontent.com/basecamp/omarchy/v4.0.0/LICENSE", payload / "LICENSE-Omarchy")
    files = {str(path.relative_to(payload)): sha256(path) for path in sorted(payload.rglob("*")) if path.is_file()}
    manifest = {"pop_shell_commit": POP_COMMIT, "fedoriri_commit": THEME_COMMIT, "files": files}
    (payload / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify_payload(payload)
    return payload


def prompt_hash():
    if not sys.stdin.isatty():
        raise ValueError("Un terminal interactif est nécessaire pour saisir le mot de passe.")
    first = getpass.getpass("Mot de passe utilisateur (12 caractères minimum) : ")
    second = getpass.getpass("Confirmer le mot de passe : ")
    if first != second or len(first) < 12 or any(char in first for char in "\n\r\x00"):
        raise ValueError("Les mots de passe doivent correspondre et comporter au moins 12 caractères.")
    result = run(["openssl", "passwd", "-6", "-stdin"], input=first + "\n", capture_output=True, text=True)
    del first, second
    return result.stdout.strip()


def assemble(source, work, payload, config, output):
    grub = work / "grub.cfg"
    run(["xorriso", "-osirrox", "on", "-indev", source, "-extract", "/boot/grub/grub.cfg", grub])
    grub.chmod(0o600)
    grub.write_text(patch_grub(grub.read_text()))
    seed = work / "autoinstall.yaml"
    seed.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    args = ["xorriso", "-indev", source, "-outdev", output,
            "-map", payload, "/payload", "-map", seed, "/autoinstall.yaml", "-map", grub, "/boot/grub/grub.cfg"]
    md5 = work / "md5sum.txt"
    run(["xorriso", "-osirrox", "on", "-indev", source, "-extract", "/md5sum.txt", md5])
    md5.chmod(0o600)
    entries = [line for line in md5.read_text().splitlines() if not line.endswith(("./boot/grub/grub.cfg", "./md5sum.txt"))]
    mapped = [(grub, "./boot/grub/grub.cfg"), (seed, "./autoinstall.yaml")]
    mapped += [(path, "./payload/" + str(path.relative_to(payload))) for path in payload.rglob("*") if path.is_file()]
    for path, name in mapped:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "md5").hexdigest()
        entries.append(f"{digest}  {name}")
    md5.write_text("\n".join(entries) + "\n")
    args += ["-map", md5, "/md5sum.txt", "-boot_image", "any", "replay", "-commit", "-end"]
    run(args)


def verify_iso(path, work, config):
    restored = work / "verification"
    restored.mkdir()
    for source, destination in [("/autoinstall.yaml", "autoinstall.yaml"), ("/boot/grub/grub.cfg", "grub.cfg"), ("/payload", "payload")]:
        run(["xorriso", "-osirrox", "on", "-indev", path, "-extract", source, restored / destination])
    if json.loads((restored / "autoinstall.yaml").read_text()) != config:
        raise ValueError("La configuration extraite de l’ISO ne correspond pas.")
    if "subiquity.autoinstallpath=cdrom/autoinstall.yaml" not in (restored / "grub.cfg").read_text():
        raise ValueError("Paramètre autoinstall absent de l’ISO produite.")
    verify_payload(restored / "payload")
    report = run(["xorriso", "-indev", path, "-report_el_torito", "plain"], capture_output=True, text=True)
    if not all(marker in report.stdout + report.stderr for marker in ("BIOS", "UEFI")):
        raise ValueError("Les entrées de démarrage BIOS et UEFI ne sont pas toutes présentes.")
    print("Contenu de l’ISO et entrées BIOS/UEFI vérifiés ; démarrage en VM encore à tester.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Préparer une ISO personnelle Ubuntu Server 24.04 AMD64, GNOME X11, Pop Shell et Citrix.", epilog="Ubuntu 24.04 requis pour construire. Réseau requis pendant l’installation. Dans Subiquity, choisir LVM et activer le chiffrement LUKS : une installation non chiffrée sera refusée avant la configuration du bureau. L’ISO contient le hash utilisateur : ne pas la publier.")
    parser._option_string_actions["--help"].help = "afficher cette aide et quitter"
    parser.add_argument("--check", action="store_true", help="vérifier uniquement les outils de construction")
    parser.add_argument("--citrix-deb", type=Path, help="paquet officiel icaclient AMD64 téléchargé depuis Citrix")
    parser.add_argument("--iso", type=Path, help="ISO officielle déjà téléchargée, vérifiée contre le manifeste signé courant")
    parser.add_argument("--username", default="ubunturiri", help="compte créé dans le système installé (défaut : ubunturiri)")
    parser.add_argument("--hostname", default="ubunturiri", help="nom de machine (défaut : ubunturiri)")
    parser.add_argument("--output", type=Path, default=ROOT / "build/ubunturiri-ubuntu24.04-amd64.iso", help="ISO de sortie, ne doit pas déjà exister")
    args = parser.parse_args(argv)
    os.umask(0o077)
    preflight()
    if args.check:
        return
    if args.citrix_deb is None:
        parser.error("--citrix-deb est requis ; fournir le paquet DEB officiel Citrix Workspace AMD64.")
    identity(args.username, args.hostname, "$6$validation$" + "a" * 86)
    output = args.output.resolve()
    partial = output.with_suffix(".partial.iso")
    if output.exists() or partial.exists():
        raise ValueError("La sortie existe déjà ; choisir un autre chemin pour éviter tout écrasement.")
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = ROOT / ".cache"
    cache.mkdir(mode=0o700, exist_ok=True)
    if shutil.disk_usage(output.parent).free < 15 * 1024 ** 3:
        raise ValueError("Prévoir au moins 15 Gio libres pour les fichiers temporaires et l’ISO.")
    print("Installation : connexion réseau, sélection du disque et phrase LUKS requises.")
    print("Le mot de passe utilisateur sera demandé après la préparation des sources.")
    try:
        with tempfile.TemporaryDirectory(prefix="iso-", dir=output.parent) as temporary:
            work = Path(temporary)
            payload = prepare_payload(work, args.citrix_deb.resolve())
            source = official_iso(cache, args.iso)
            config = autoinstall(args.username, args.hostname, prompt_hash())
            assemble(source, work, payload, config, partial)
            verify_iso(partial, work, config)
            partial.chmod(0o600)
            partial.replace(output)
            output.with_suffix(".iso.sha256").write_text(f"{sha256(output)}  {output.name}\n")
    finally:
        partial.unlink(missing_ok=True)
    print(f"ISO créée et contrôlée : {output}")
    print("Conserver cette ISO privée. Test d’installation en VM et test Citrix réel à effectuer.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Construction interrompue.", file=sys.stderr)
        sys.exit(130)
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print(f"Construction arrêtée : {error}", file=sys.stderr)
        sys.exit(1)
