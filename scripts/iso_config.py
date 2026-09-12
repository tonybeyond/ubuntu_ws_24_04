#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path


def identity(username, hostname, password_hash):
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", username):
        raise ValueError("Nom utilisateur invalide.")
    if username in {"root", "daemon", "nobody", "ubuntu"}:
        raise ValueError("Choisir un nom utilisateur non réservé.")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", hostname):
        raise ValueError("Nom de machine invalide.")
    if not re.fullmatch(r"\$6\$[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{86}", password_hash):
        raise ValueError("Empreinte du mot de passe invalide.")
    return {"username": username, "hostname": hostname, "password": password_hash}


def autoinstall(username, hostname, password_hash):
    return {"autoinstall": {
        "version": 1,
        "refresh-installer": {"update": False},
        "locale": "fr_CH.UTF-8",
        "keyboard": {"layout": "ch", "variant": "fr"},
        "source": {"id": "ubuntu-server-minimal", "search_drivers": False},
        "identity": identity(username, hostname, password_hash),
        "interactive-sections": ["network", "storage"],
        "storage": {"layout": {"name": "lvm", "sizing-policy": "all"}},
        "ssh": {"install-server": False, "allow-pw": False},
        "apt": {"geoip": False, "fallback": "abort"},
        "updates": "security",
        "shutdown": "poweroff",
        "early-commands": [["python3", "/cdrom/payload/iso_config.py", "verify-payload", "/cdrom/payload"]],
        "late-commands": [
            ["python3", "/cdrom/payload/iso_config.py", "verify-encryption", "/target"],
            ["mkdir", "-p", "/target/opt/fedoriri"],
            ["cp", "-a", "/cdrom/payload/.", "/target/opt/fedoriri/"],
            ["curtin", "in-target", "--target=/target", "--", "bash", "/opt/fedoriri/install-desktop.sh", username],
        ],
    }}


def patch_grub(text):
    lines = []
    count = 0
    for line in text.splitlines(keepends=True):
        if re.match(r"\s*linux(?:efi)?\s+/casper/(?:hwe-)?vmlinuz(?:\s|$)", line):
            if "autoinstall" in line:
                raise ValueError("La configuration GRUB est déjà personnalisée.")
            if "---" not in line:
                raise ValueError("Ligne de démarrage Ubuntu inattendue.")
            line = line.replace("---", "autoinstall subiquity.autoinstallpath=cdrom/autoinstall.yaml ---", 1)
            count += 1
        lines.append(line)
    if not count:
        raise ValueError("Aucune entrée Ubuntu Server reconnue dans GRUB.")
    return "".join(lines)


def encrypted_tree(node, crypt=False, luks=False):
    crypt = crypt or node.get("type") == "crypt"
    luks = luks or node.get("fstype") == "crypto_LUKS"
    children = node.get("children", [])
    if not children:
        return crypt and luks
    return all(encrypted_tree(child, crypt, luks) for child in children)


def verify_encryption(target):
    source = subprocess.check_output(["findmnt", "-n", "-o", "SOURCE", "--target", target], text=True).strip()
    if not source.startswith("/dev/"):
        raise ValueError("La racine installée ne repose pas sur un périphérique bloc.")
    source = source.split("[", 1)[0]
    tree = json.loads(subprocess.check_output(["lsblk", "--inverse", "--json", "--paths", "--output", "NAME,TYPE,FSTYPE", source], text=True))
    nodes = tree.get("blockdevices", [])
    if not nodes or not all(encrypted_tree(node) for node in nodes):
        raise ValueError("Installation refusée : la racine doit être sur LUKS. Activer le chiffrement dans le partitionnement.")
    entries = [line.split() for line in (Path(target) / "etc/crypttab").read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not entries or any(len(entry) < 3 or entry[2] not in {"none", "-"} for entry in entries):
        raise ValueError("Une phrase de passe au démarrage est requise, sans fichier de clé.")
    print("Racine LUKS et déverrouillage par phrase de passe vérifiés.")


def verify_payload(directory):
    import hashlib
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    expected = manifest["files"]
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Lien symbolique interdit dans le contenu embarqué.")
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and path != root / "manifest.json"}
    if actual != set(expected):
        raise ValueError("Le contenu embarqué ne correspond pas au manifeste.")
    for name, digest in expected.items():
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError("Chemin interdit dans le contenu embarqué.")
        with path.open("rb") as stream:
            value = hashlib.file_digest(stream, "sha256").hexdigest()
        if value != digest:
            raise ValueError("Contrôle SHA-256 du contenu embarqué en échec.")
    print("Intégrité du contenu embarqué vérifiée.")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in {"verify-encryption", "verify-payload"}:
        raise ValueError("Usage : iso_config.py verify-encryption|verify-payload CHEMIN")
    if sys.argv[1] == "verify-encryption":
        verify_encryption(sys.argv[2])
    else:
        verify_payload(sys.argv[2])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        sys.exit(1)
