#!/usr/bin/env python3
"""Composants absents des dépôts Ubuntu 24.04, épinglés par URL et SHA-256.

Chaque entrée est téléchargée à la construction, vérifiée contre son empreinte,
puis embarquée dans l'ISO. Aucun dépôt tiers n'est ajouté au système installé,
à l'exception de Brave : le paquet brave-origin dépend de brave-keyring, qui
installe lui-même la clé du dépôt. Voir README.md, section « Paquets tiers ».

Pour changer de version : modifier url et version, puis lancer
python3 scripts/refresh_pins.py --write pour recalculer les empreintes.
"""

PINS = {
    "extras/ghostty.deb": {
        "version": "1.3.1~ppa2-noble1",
        "url": "https://ppa.launchpadcontent.net/mkasberg/ghostty-ubuntu/ubuntu/pool/main/g/ghostty/ghostty_1.3.1~ppa2-noble1_amd64.deb",
        "sha256": "81c23abd33a58ba0a322a7a082fadea0fd63128bb990c50ec98622e804249b3d",
        "note": "PPA mkasberg/ghostty-ubuntu, série noble ; empreinte identique au champ SHA256 de l'index Packages du PPA",
    },
    "extras/netbird.deb": {
        "version": "0.78.1",
        "url": "https://pkgs.netbird.io/debian/pool/netbird_0.78.1_linux_amd64.deb",
        "sha256": "c461cfa27426e346c2479ec6dc83803a812dfcec135eb0f67a4dce0da75ad5db",
        "note": "démon et CLI ; empreinte identique au champ SHA256 de l'index pkgs.netbird.io",
    },
    "extras/netbird-ui.deb": {
        "version": "0.78.1",
        "url": "https://pkgs.netbird.io/debian/pool/netbird-ui_0.78.1_linux_amd64.deb",
        "sha256": "e8f034e603189e82cc9c9c8051e01c60d7e6cb7d9f7f2b68c08328950b486dab",
        "note": "icône de barre d'état GTK4 ; dépend de libgtk-4-1 et libwebkitgtk-6.0-4, tous deux dans noble main",
    },
    "extras/fastfetch.deb": {
        "version": "2.64.2",
        "url": "https://github.com/fastfetch-cli/fastfetch/releases/download/2.64.2/fastfetch-linux-amd64.deb",
        "sha256": "af061369d6413677f55f01517b21c029207503e845a4575d3f128b75a425f83f",
        "note": "absent de noble ; neofetch y est présent mais n'est plus maintenu en amont",
    },
    "extras/nvim.tar.gz": {
        "version": "0.12.5",
        "url": "https://github.com/neovim/neovim/releases/download/v0.12.5/nvim-linux-x86_64.tar.gz",
        "sha256": "bce0f56eda1f1b1db6eee8f4133d7a38813ea07933837dd1777411ca384c6875",
        "note": "noble ne fournit que 0.9.5, sous le minimum de lazy.nvim et LazyVim",
    },
    "extras/starship.tar.gz": {
        "version": "1.25.1",
        "url": "https://github.com/starship/starship/releases/download/v1.25.1/starship-x86_64-unknown-linux-gnu.tar.gz",
        "sha256": "4488c11ca632327d1f1f16fb2f102c0646094c35479cd5435991385da43c61ac",
        "note": "absent de tous les dépôts Ubuntu 24.04",
    },
    "extras/blesh.tar.xz": {
        "version": "0.4.0-devel3",
        "url": "https://github.com/akinomyoga/ble.sh/releases/download/v0.4.0-devel3/ble-0.4.0-devel3.tar.xz",
        "sha256": "c8612ee612bc6b10dbfd6e85c6cbdfd7caf152a12d1f9de22ea0a9d735b3080c",
        "note": "équivalent bash de zsh-autosuggestions et zsh-syntax-highlighting",
    },
    "extras/jetbrains-mono-nerd-font.tar.xz": {
        "version": "3.5.1",
        "url": "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/JetBrainsMono.tar.xz",
        "sha256": "04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf",
        "note": "fonts-jetbrains-mono de noble n'a pas les glyphes Nerd Font exigés par Starship et eza --icons",
    },
    "extras/brave-browser-archive-keyring.gpg": {
        "version": "2025-07-30",
        "url": "https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg",
        "sha256": "c85e85aa3d1783ffaa649ee8dbbc22af7f87192d304602d37e3018226b394788",
        "note": "octet pour octet le même fichier que celui embarqué dans le paquet brave-keyring",
    },
}

# Paquets APT, groupés pour rester lisibles dans install-desktop.sh.
# Tous vérifiés présents dans les index Noble AMD64 par tests/check_packages.py.
APT_GROUPS = {
    "libreoffice": [
        "libreoffice-writer",
        "libreoffice-calc",
        "libreoffice-impress",
        "libreoffice-draw",
        "libreoffice-gtk3",
        "libreoffice-l10n-fr",
        "libreoffice-help-fr",
        "hunspell-fr",
        "mythes-fr",
        "hyphen-fr",
        "fonts-liberation",
    ],
    "shell": [
        "eza",
        "zoxide",
        "fzf",
        "ripgrep",
        "fd-find",
        "bat",
        "jq",
        "tmux",
        "aria2",
    ],
}

# Dépôt Brave. brave-origin dépend de brave-keyring, qui écrit lui-même la clé
# dans /usr/share/keyrings ; poser la source à l'avance évite un apt-get update
# supplémentaire et garde le contrôle du fichier deb822.
BRAVE_SOURCE = """Types: deb
URIs: https://brave-browser-apt-release.s3.brave.com
Suites: stable
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/brave-browser-archive-keyring.gpg
"""

BRAVE_PACKAGE = "brave-origin"


def apt_list(group):
    if group not in APT_GROUPS:
        raise ValueError(f"Groupe de paquets inconnu : {group}")
    return " ".join(APT_GROUPS[group])


def main():
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "--brave-source":
        print(BRAVE_SOURCE, end="")
    elif len(sys.argv) == 2 and sys.argv[1] == "--brave-package":
        print(BRAVE_PACKAGE)
    elif len(sys.argv) == 3 and sys.argv[1] == "--apt":
        print(apt_list(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == "--pins":
        for name, pin in PINS.items():
            print(f"{name}\t{pin['version']}\t{pin['sha256']}")
    else:
        raise ValueError("Usage : packages.py --apt GROUPE | --brave-source | --brave-package | --pins")


if __name__ == "__main__":
    import sys

    try:
        main()
    except ValueError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        sys.exit(1)
