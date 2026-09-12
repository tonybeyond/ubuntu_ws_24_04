#!/usr/bin/env python3
"""Pose le bashrc Starship, la configuration Ghostty et le prompt utilisateur.

Appelé deux fois par install-desktop.sh : une fois en root pour /etc/skel et le
profil système, une fois sous le compte utilisateur pour ses propres fichiers.
"""
import os
import pwd
import shutil
import sys
from pathlib import Path

PAYLOAD = Path("/opt/ubunturiri")
FILES = PAYLOAD / "files"
SKEL = Path("/etc/skel")


def write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def copy(source, destination, mode=0o644):
    if not source.is_file():
        raise ValueError(f"Fichier absent du contenu embarqué : {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(mode)


def layout(home):
    return [
        (FILES / "bashrc", home / ".bashrc", 0o644),
        (FILES / "starship.toml", home / ".config/starship.toml", 0o644),
        (FILES / "ghostty-config", home / ".config/ghostty/config", 0o644),
    ]


def system(username):
    if os.geteuid() != 0:
        raise ValueError("Configuration système réservée à l’installation.")
    entry = pwd.getpwnam(username)
    if not Path("/usr/share/blesh/ble.sh").is_file():
        raise ValueError("ble.sh absent : l’installation du shell a échoué plus tôt.")
    if not shutil.which("starship"):
        raise ValueError("starship introuvable dans le PATH système.")
    for source, destination, mode in layout(SKEL):
        copy(source, destination, mode)
    # Le shell de connexion reste bash ; seul son contenu change.
    if entry.pw_shell not in {"/bin/bash", "/usr/bin/bash"}:
        raise ValueError(f"Shell inattendu pour {username} : {entry.pw_shell}")
    write(Path("/etc/profile.d/99-ubunturiri-nvim.sh"), 'export PATH="/opt/nvim/bin:$PATH"\n', 0o644)
    print("Squelette shell et PATH Neovim posés.")


def configure_user():
    if os.geteuid() == 0:
        raise ValueError("Configurer le shell avec le compte utilisateur, pas root.")
    home = Path.home()
    for source, destination, mode in layout(home):
        if destination.exists() and destination.name == ".bashrc":
            backup = home / ".bashrc.ubuntu-origine"
            if not backup.exists():
                shutil.copyfile(destination, backup)
        copy(source, destination, mode)
    write(home / ".bashrc.local", "# Ajouts personnels, préservés lors d’une réinstallation du profil.\n", 0o644)
    print("Shell utilisateur configuré.")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "system":
        system(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "user":
        configure_user()
    else:
        raise ValueError("Usage : shell_setup.py system UTILISATEUR | user")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f"Configuration du shell arrêtée : {error}", file=sys.stderr)
        sys.exit(1)
