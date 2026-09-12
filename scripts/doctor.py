#!/usr/bin/env python3
"""Vérifie que le poste est bien ce que le profil prétend avoir installé.

À lancer sans privilèges, dans une session graphique de préférence :

    ubunturiri-doctor          contrôles, un par ligne
    ubunturiri-doctor --quiet  n'affiche que les échecs

Sort en 0 si tout passe, en 1 sinon. Chaque échec dit quoi faire.

Ce contrôle existe parce qu'une installation peut s'arrêter en cours de route
sans que rien ne le montre : GDM s'active tout seul, un bureau apparaît, et
les dernières étapes du profil n'ont pourtant jamais tourné.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PAYLOAD = Path("/opt/ubunturiri")
VERT, ROUGE, JAUNE, NEUTRE = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


class Rapport:
    def __init__(self, quiet=False):
        self.quiet = quiet
        self.echecs = []
        self.ignores = 0
        self.couleur = sys.stdout.isatty()

    def _ecrire(self, marque, couleur, categorie, libelle, detail):
        if self.couleur:
            marque = f"{couleur}{marque}{NEUTRE}"
        ligne = f"  {marque}  {categorie:<12} {libelle}"
        if detail:
            ligne += f"\n                   {detail}"
        print(ligne)

    def ok(self, categorie, libelle, detail=""):
        if not self.quiet:
            self._ecrire("OK ", VERT, categorie, libelle, detail)

    def echec(self, categorie, libelle, remede):
        self.echecs.append((categorie, libelle, remede))
        self._ecrire("NON", ROUGE, categorie, libelle, remede)

    def ignore(self, categorie, libelle, raison):
        self.ignores += 1
        if not self.quiet:
            self._ecrire("—  ", JAUNE, categorie, libelle, raison)

    def verdict(self):
        print()
        if self.echecs:
            print(f"{len(self.echecs)} contrôle(s) en échec.")
            return 1
        suffixe = f", {self.ignores} non évalué(s)" if self.ignores else ""
        print(f"Tout est conforme au profil{suffixe}.")
        return 0


def sortie(commande):
    """Renvoie la sortie d'une commande, ou None si elle échoue ou n'existe pas."""
    try:
        resultat = subprocess.run(commande, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return resultat.stdout.strip() if resultat.returncode == 0 else None


def etat_unite(unite):
    """État d'une unité systemd, y compris quand la commande sort en erreur.

    « systemctl is-enabled » renvoie 1 pour une unité masquée ou désactivée et
    4 pour une unité inexistante, tout en écrivant l'état sur la sortie
    standard. Se fier au seul code de retour ferait passer « masked » pour une
    absence d'information.
    """
    try:
        resultat = subprocess.run(["systemctl", "is-enabled", unite],
                                  capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    etat = resultat.stdout.strip()
    return etat or None


def etat_chemin(chemin):
    """« present », « illisible » ou « absent », sans jamais lever.

    Path.exists() relaie PermissionError quand un dossier parent n'est pas
    traversable : un simple contrôle de présence faisait planter la commande
    entière. Et un fichier présent mais illisible est le cas le plus sournois,
    puisque le bashrc le saute sans rien dire.
    """
    chemin = Path(chemin)
    try:
        if not chemin.exists():
            return "absent"
    except OSError:
        return "illisible"
    try:
        with chemin.open("rb"):
            return "present"
    except IsADirectoryError:
        return "present"
    except OSError:
        return "illisible"


def gsettings(schema, cle):
    return sortie(["gsettings", "get", schema, cle])


def controler_session(r):
    session = os.environ.get("XDG_SESSION_TYPE")
    if session is None:
        r.ignore("session", "type de session", "hors session graphique ; relancer depuis le bureau")
    elif session == "x11":
        r.ok("session", "session X11 active")
    else:
        r.echec("session", f"session {session} au lieu de X11",
                "Citrix attend X11. Vérifier WaylandEnable=false dans /etc/gdm3/custom.conf")

    custom = Path("/etc/gdm3/custom.conf")
    texte = custom.read_text() if custom.is_file() else ""
    if "WaylandEnable=false" in texte.replace(" ", "") and "gnome-xorg" in texte:
        r.ok("session", "GDM configuré en gnome-xorg sans Wayland")
    else:
        r.echec("session", "GDM non configuré par le profil",
                "session_setup.py n'a pas tourné : l'installation s'est arrêtée avant la fin")


def controler_popshell(r):
    metadata = Path("/usr/share/gnome-shell/extensions/pop-shell@system76.com/metadata.json")
    if not metadata.is_file():
        r.echec("pavage", "Pop Shell non installé", "la compilation a échoué pendant l'installation")
        return
    r.ok("pavage", "Pop Shell installé")
    actives = gsettings("org.gnome.shell", "enabled-extensions")
    if actives is None:
        r.ignore("pavage", "extension activée", "gsettings indisponible hors session")
    elif "pop-shell@system76.com" in actives:
        r.ok("pavage", "Pop Shell activé pour la session")
    else:
        r.echec("pavage", "Pop Shell installé mais non activé",
                "gnome-extensions enable pop-shell@system76.com")


def controler_reseau(r):
    if Path("/etc/netplan/99-ubunturiri-renderer.yaml").is_file():
        r.ok("réseau", "rendu netplan confié à NetworkManager")
    else:
        r.echec("réseau", "fichier netplan du profil absent",
                "session_setup.py n'a pas tourné")

    etat = etat_unite("systemd-networkd-wait-online.service")
    if etat == "masked":
        r.ok("réseau", "attente systemd-networkd retirée")
    else:
        r.echec("réseau", f"systemd-networkd-wait-online est « {etat or 'actif'} »",
                "sudo systemctl mask systemd-networkd-wait-online.service ; il retarde chaque démarrage")


def controler_police(r):
    dossier = Path("/usr/local/share/fonts/JetBrainsMonoNerdFont")
    fichiers = sorted(dossier.glob("JetBrainsMonoNerdFontMono-*.ttf")) if dossier.is_dir() else []
    if len(fichiers) < 8:
        r.echec("police", f"{len(fichiers)} fichier(s) de police Nerd Font",
                "les glyphes de Starship et de eza --icons ne s'afficheront pas")
        return
    familles = sortie(["fc-list", ":family"]) or ""
    if "JetBrainsMono Nerd Font" in familles:
        r.ok("police", f"JetBrainsMono Nerd Font enregistrée ({len(fichiers)} fichiers)")
    else:
        r.echec("police", "police présente mais inconnue de fontconfig",
                "fc-cache -f /usr/local/share/fonts/JetBrainsMonoNerdFont")


def controler_shell(r):
    for nom, chemin in [("Starship", "/usr/local/bin/starship"), ("ble.sh", "/usr/share/blesh/ble.sh")]:
        etat = etat_chemin(chemin)
        if etat == "present":
            r.ok("shell", f"{nom} installé")
        elif etat == "illisible":
            # Le bashrc se contente de tester la présence : une permission trop
            # stricte le fait sauter la source sans le moindre message.
            r.echec("shell", f"{nom} installé mais illisible pour votre compte",
                    f"sudo chmod -R a+rX {Path(chemin).parent} ; sinon il est ignoré en silence")
        else:
            r.echec("shell", f"{nom} absent", f"attendu dans {chemin}")

    bashrc = Path.home() / ".bashrc"
    contenu = bashrc.read_text(errors="replace") if bashrc.is_file() else ""
    if "starship init bash" in contenu and "ble.sh" in contenu:
        r.ok("shell", "bashrc du profil en place")
    else:
        r.echec("shell", "bashrc du profil absent du compte",
                "shell_setup.py n'a pas tourné ; ~/.bashrc.ubuntu-origine garde l'original")

    config = Path.home() / ".config/starship.toml"
    if config.is_file():
        r.ok("shell", "starship.toml présent")
    else:
        r.echec("shell", "starship.toml absent", "le prompt retombera sur le thème par défaut")


def controler_applications(r):
    attendus = [
        ("nvim", ["/usr/local/bin/nvim", "--version"], "Neovim"),
        ("ghostty", ["/usr/bin/ghostty", "--version"], "Ghostty"),
        ("brave", ["/usr/bin/brave-origin-stable", "--version"], "Brave Origin"),
        ("netbird", ["/usr/bin/netbird", "version"], "NetBird"),
        ("libreoffice", ["/usr/bin/libreoffice", "--version"], "LibreOffice"),
        ("fastfetch", ["/usr/bin/fastfetch", "--version"], "fastfetch"),
    ]
    for categorie, commande, nom in attendus:
        etat = etat_chemin(commande[0])
        if etat == "absent":
            r.echec("applications", f"{nom} absent", f"attendu en {commande[0]}")
            continue
        if etat == "illisible":
            r.echec("applications", f"{nom} installé mais inaccessible",
                    f"sudo chmod -R a+rX {Path(commande[0]).parent}")
            continue
        version = sortie(commande)
        premiere = version.splitlines()[0] if version else "version illisible"
        r.ok("applications", f"{nom} : {premiere}")

    if shutil.which("hunspell") or etat_chemin("/usr/share/hunspell/fr_FR.dic") == "present":
        r.ok("applications", "dictionnaire français installé")
    else:
        r.echec("applications", "dictionnaire français absent",
                "LibreOffice n'aura pas de correcteur en fr_CH")


def controler_lsp(r):
    for binaire, role in [("pylsp", "Python"), ("ruff", "Python, lint et format"), ("marksman", "Markdown")]:
        if shutil.which(binaire):
            r.ok("neovim", f"serveur LSP {binaire} ({role})")
        else:
            r.echec("neovim", f"serveur LSP {binaire} absent",
                    f"la configuration Neovim l'active pour {role}")

    # nvim-treesitter branche main appelle « tree-sitter build » : sans le
    # binaire, chaque démarrage affiche une erreur ENOENT et aucun analyseur
    # n'est compilé. Le paquet de noble, en 0.20.8, est sous le minimum de
    # 0.26.1 exigé en amont.
    version = sortie(["tree-sitter", "--version"])
    if version is None:
        r.echec("neovim", "CLI tree-sitter absent",
                "nvim-treesitter ne peut compiler aucun analyseur ; erreur ENOENT à chaque démarrage")
    else:
        numero = version.split()[-1]
        composants = [int(n) for n in numero.split(".")[:2] if n.isdigit()]
        if composants < [0, 26]:
            r.echec("neovim", f"CLI tree-sitter {numero}, trop ancien",
                    "nvim-treesitter branche main exige 0.26.1 au minimum")
        else:
            r.ok("neovim", f"CLI tree-sitter {numero}")

    analyseurs = sorted(
        chemin.stem
        for base in [Path.home() / ".local/share/nvim/site/parser"]
        if base.is_dir()
        for chemin in base.glob("*.so")
    )
    if analyseurs:
        r.ok("neovim", f"analyseurs Treesitter compilés : {', '.join(analyseurs)}")
    else:
        r.ignore("neovim", "analyseurs Treesitter",
                 "aucun compilé ; ils le seront au prochain démarrage de nvim, avec réseau")

    config = Path.home() / ".config/nvim/init.lua"
    if config.is_file():
        r.ok("neovim", "configuration Neovim du profil en place")
    else:
        r.echec("neovim", "configuration Neovim absente", "attendue en ~/.config/nvim/init.lua")
        return

    verrou = Path.home() / ".config/nvim/nvim-pack-lock.json"
    if not verrou.is_file():
        r.ignore("neovim", "greffons Neovim", "jamais démarré ; ils s'installeront au premier lancement")
        return
    try:
        données = json.loads(verrou.read_text())
        nombre = len(données.get("plugins", données)) if isinstance(données, dict) else len(données)
        r.ok("neovim", f"{nombre} greffon(s) verrouillés dans nvim-pack-lock.json")
    except (json.JSONDecodeError, OSError, TypeError):
        r.echec("neovim", "verrou vim.pack illisible", "supprimer le fichier et relancer nvim")


def controler_maintenance(r):
    if etat_chemin("/usr/bin/unattended-upgrade") != "absent":
        etat = etat_unite("unattended-upgrades.service")
        if etat == "enabled":
            r.ok("maintenance", "mises à jour de sécurité automatiques actives")
        else:
            r.echec("maintenance", f"unattended-upgrades « {etat or 'inactif'} »",
                    "sudo systemctl enable --now unattended-upgrades.service")
    else:
        r.echec("maintenance", "unattended-upgrades absent", "aucune mise à jour de sécurité automatique")

    journal = Path("/var/log/ubunturiri-install.log")
    if not journal.is_file():
        r.ignore("maintenance", "journal d'installation", "absent ; ISO antérieure à la journalisation")
        return
    texte = journal.read_text(errors="replace")
    avertissements = [l for l in texte.splitlines() if l.startswith(("ECHEC", "Avertissement"))]
    if avertissements:
        r.echec("maintenance", f"{len(avertissements)} alerte(s) dans le journal d'installation",
                f"la première : {avertissements[0][:90]}")
    else:
        r.ok("maintenance", "journal d'installation sans alerte")


def main():
    parser = argparse.ArgumentParser(description="Contrôler la conformité du poste au profil ubunturiri.")
    parser.add_argument("--quiet", action="store_true", help="n'afficher que les échecs")
    args = parser.parse_args()

    # Aucun contrôle n'exige de privilèges, et la moitié porte sur le compte :
    # sous sudo, Path.home() vaut /root et gsettings lit la configuration de
    # root. Les contrôles shell, Neovim et Pop Shell rendraient alors un verdict
    # faux. Mieux vaut refuser que mentir.
    if os.geteuid() == 0:
        compte = os.environ.get("SUDO_USER")
        print("ubunturiri-doctor ne doit pas être lancé en root : les contrôles du shell,",
              "de Neovim et de Pop Shell porteraient sur le compte root, pas sur le vôtre.",
              sep="\n", file=sys.stderr)
        if compte:
            print(f"\nRelancer simplement :  ubunturiri-doctor", file=sys.stderr)
        return 2

    r = Rapport(quiet=args.quiet)
    if not args.quiet:
        print("\nContrôle du profil ubunturiri\n")
    for controle in [controler_session, controler_popshell, controler_reseau, controler_police,
                     controler_shell, controler_applications, controler_lsp, controler_maintenance]:
        controle(r)
    return r.verdict()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
