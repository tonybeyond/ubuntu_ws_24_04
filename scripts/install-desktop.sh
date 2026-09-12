#!/usr/bin/env bash
set +x
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export PYTHONDONTWRITEBYTECODE=1
USER_NAME="${1:?Nom utilisateur requis}"
PAYLOAD=/opt/ubunturiri
LOG=/var/log/ubunturiri-install.log
[[ "$EUID" -eq 0 ]] || { printf '%s\n' 'Exécuter dans la cible Ubuntu avec les droits administrateur.' >&2; exit 1; }

# Subiquity n'affiche qu'un rapport de plantage, et la sortie réelle du script
# part dans le journal du système live sous subiquity_log.<pid>. Ce journal-ci
# vit dans la cible : lisible en /target/var/log/ pendant l'installation, en
# /var/log/ après redémarrage, y compris quand l'installation a échoué.
#
# La substitution de processus exige /dev/fd, donc /proc monté dans le chroot.
# Curtin le monte, mais une redirection exec qui échoue tuerait le script avant
# la première étape : vérifier avant, et continuer sans journal plutôt que
# d'introduire une panne à la place de celle qu'on diagnostique.
if mkdir -p "$(dirname "$LOG")" 2>/dev/null && : >> "$LOG" 2>/dev/null && [[ -e /dev/fd/1 ]]; then
  exec > >(tee -a "$LOG") 2>&1
else
  printf '%s\n' "Journalisation dans $LOG impossible ; poursuite sans duplication." >&2
  LOG='(indisponible)'
fi

step() {
  printf '\n=== ubunturiri : %s ===\n' "$1"
}

on_error() {
  local status=$? line=$1 command=$2
  printf '\nECHEC ubunturiri : ligne %s, code %s\n  commande : %s\n  journal  : %s\n' \
    "$line" "$status" "$command" "$LOG" >&2
  exit "$status"
}
trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR
python3 "$PAYLOAD/iso_config.py" verify-payload "$PAYLOAD"
chmod -R a+rX "$PAYLOAD"
python3 -c 'import platform; r=platform.freedesktop_os_release(); assert r.get("ID")=="ubuntu" and r.get("VERSION_ID")=="24.04", "Ubuntu 24.04 requis"'
[[ "$(dpkg --print-architecture)" == amd64 ]] || { printf '%s\n' 'Cible AMD64 requise pour Citrix.' >&2; exit 1; }
id "$USER_NAME" >/dev/null
step 'Bureau minimal et dépendances Citrix'
apt-get update
apt-get install --no-install-recommends -y \
  gnome-session gnome-shell gdm3 gnome-settings-daemon gnome-control-center \
  gnome-keyring gnome-shell-extension-prefs gnome-shell-extension-appindicator \
  gnome-terminal nautilus gvfs-backends network-manager network-manager-gnome \
  dbus-x11 xserver-xorg x11-xserver-utils x11-utils xauth \
  pipewire pipewire-pulse wireplumber libspa-0.2-bluetooth bluez \
  fonts-dejavu-core fonts-noto-color-emoji fonts-firacode \
  mesa-va-drivers mesa-utils vainfo gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav libsecret-1-0 net-tools libwebkit2gtk-4.1-0 \
  ca-certificates curl xdg-utils libnotify-bin dconf-cli \
  git build-essential node-typescript btop bash-completion unzip python3 \
  xz-utils fontconfig
apt-get install --no-install-recommends -y "$PAYLOAD/icaclient.deb"
[[ "$(dpkg-query -W -f='${Status}' icaclient)" == 'install ok installed' ]]
[[ -x /opt/Citrix/ICAClient/wfica ]]
if ldd /opt/Citrix/ICAClient/wfica | grep -q 'not found'; then
  printf '%s\n' 'Bibliothèques Citrix manquantes : installation arrêtée, sans contournement ABI.' >&2
  exit 1
fi
if [[ -x /opt/Citrix/ICAClient/util/ctx_rehash ]]; then
  /opt/Citrix/ICAClient/util/ctx_rehash
fi
step 'Compilation de Pop Shell pour GNOME 46'
POP_BUILD="$(mktemp -d /tmp/ubunturiri-pop.XXXXXX)"
trap 'rm -rf -- "$POP_BUILD"' EXIT
cp -a "$PAYLOAD/pop-shell/." "$POP_BUILD/"
make -C "$POP_BUILD" all
make -C "$POP_BUILD" DESTDIR=/ install
[[ -f /usr/share/gnome-shell/extensions/pop-shell@system76.com/metadata.json ]]
step 'LibreOffice et dictionnaires français'
apt-get install --no-install-recommends -y $(python3 "$PAYLOAD/packages.py" --apt libreoffice)
[[ -x /usr/bin/libreoffice ]]

step 'Outils en ligne de commande'
apt-get install --no-install-recommends -y $(python3 "$PAYLOAD/packages.py" --apt shell)
for binary in eza zoxide fzf rg fdfind batcat jq tmux aria2c; do
  command -v "$binary" >/dev/null || { printf '%s\n' "Binaire attendu absent après installation : $binary" >&2; exit 1; }
done

step 'Paquets DEB embarqués : Ghostty, NetBird, fastfetch'
apt-get install --no-install-recommends -y \
  "$PAYLOAD/extras/ghostty.deb" \
  "$PAYLOAD/extras/netbird.deb" \
  "$PAYLOAD/extras/netbird-ui.deb" \
  "$PAYLOAD/extras/fastfetch.deb"
for package in ghostty netbird netbird-ui fastfetch; do
  [[ "$(dpkg-query -W -f='${Status}' "$package")" == 'install ok installed' ]] || { printf '%s\n' "Paquet non installé : $package" >&2; exit 1; }
done
for binary in /usr/bin/ghostty /usr/bin/netbird /usr/bin/fastfetch; do
  if ldd "$binary" 2>/dev/null | grep -q 'not found'; then
    printf '%s\n' "Bibliothèques manquantes pour $binary : installation arrêtée." >&2
    exit 1
  fi
done
# Le service netbird est activé mais le poste n'est enrôlé dans aucun réseau :
# lancer netbird up --setup-key après le premier démarrage.
systemctl enable netbird.service

step 'Neovim depuis l’archive amont épinglée'
rm -rf /opt/nvim
mkdir -p /opt/nvim
tar -xzf "$PAYLOAD/extras/nvim.tar.gz" -C /opt/nvim --strip-components=1
[[ -x /opt/nvim/bin/nvim ]]
ln -sfn /opt/nvim/bin/nvim /usr/local/bin/nvim
/usr/local/bin/nvim --version | head -n1
update-alternatives --install /usr/bin/editor editor /opt/nvim/bin/nvim 60

step 'Starship et ble.sh'
tar -xzf "$PAYLOAD/extras/starship.tar.gz" -C /usr/local/bin starship
chmod 0755 /usr/local/bin/starship
/usr/local/bin/starship --version >/dev/null
BLE_BUILD="$(mktemp -d /tmp/ubunturiri-ble.XXXXXX)"
tar -xJf "$PAYLOAD/extras/blesh.tar.xz" -C "$BLE_BUILD" --strip-components=1
rm -rf /usr/share/blesh
mkdir -p /usr/share/blesh
cp -a "$BLE_BUILD/." /usr/share/blesh/
rm -rf -- "$BLE_BUILD"
[[ -f /usr/share/blesh/ble.sh ]]

step 'Police JetBrainsMono Nerd Font'
FONT_DIR=/usr/local/share/fonts/JetBrainsMonoNerdFont
rm -rf "$FONT_DIR"
mkdir -p "$FONT_DIR"
# Seule la variante Mono est retenue : chasse fixe pour les glyphes, et
# l'archive complète pèse 79 Mio contre 39 Mio pour cette variante seule.
tar -xJf "$PAYLOAD/extras/jetbrains-mono-nerd-font.tar.xz" -C "$FONT_DIR" \
  --wildcards 'JetBrainsMonoNerdFontMono-*.ttf' 'OFL.txt'
chmod -R a+rX "$FONT_DIR"

# Ce que cette étape doit garantir : les fichiers sont en place et lisibles.
# La famille est lue directement dans le fichier avec fc-scan, sans passer par
# le cache ni la configuration de fontconfig, qui ne se comportent pas de la
# même façon dans le chroot de l'installateur que sur un système démarré.
# Le contrôle précédent, « fc-list | grep », y échouait alors que les polices
# étaient correctement installées, et arrêtait toute l'installation.
FONT_COUNT="$(find "$FONT_DIR" -name 'JetBrainsMonoNerdFontMono-*.ttf' -type f | wc -l)"
if [[ "$FONT_COUNT" -lt 8 ]]; then
  printf '%s\n' "Police : $FONT_COUNT fichier(s) extrait(s) dans $FONT_DIR, 8 au minimum attendus." >&2
  exit 1
fi
fc-scan --format '%{family}\n' "$FONT_DIR/JetBrainsMonoNerdFontMono-Regular.ttf" \
  | grep -q 'JetBrainsMono Nerd Font Mono' || {
    printf '%s\n' 'Police : la famille lue dans le fichier ne correspond pas à JetBrainsMono Nerd Font Mono.' >&2
    exit 1
  }
printf 'Police : %s fichiers installés, famille vérifiée dans le fichier.\n' "$FONT_COUNT"

# fc-cache accélère la prise en compte, sans être nécessaire : fontconfig
# indexe le répertoire à l'ouverture de session. Son échec dans le chroot ne
# doit donc pas interrompre l'installation.
if ! fc-cache -f "$FONT_DIR" >/dev/null 2>&1; then
  printf '%s\n' 'Avertissement : fc-cache a échoué dans le chroot ; enregistrement reporté au premier démarrage.' >&2
fi

step 'Serveurs LSP pour Neovim'
apt-get install --no-install-recommends -y $(python3 "$PAYLOAD/packages.py" --apt neovim)
tar -xzf "$PAYLOAD/extras/ruff.tar.gz" -C /usr/local/bin --strip-components=1 \
  ruff-x86_64-unknown-linux-gnu/ruff
chmod 0755 /usr/local/bin/ruff
install -m 0755 "$PAYLOAD/extras/marksman" /usr/local/bin/marksman
# nvim-treesitter branche main appelle « tree-sitter build » pour compiler les
# analyseurs ; sans ce binaire, chaque démarrage de Neovim affiche une erreur
# ENOENT. Le paquet tree-sitter-cli de noble est en 0.20.8, sous le minimum de
# 0.26.1 exigé par nvim-treesitter : il faut la version amont.
gunzip -c "$PAYLOAD/extras/tree-sitter.gz" > /usr/local/bin/tree-sitter
chmod 0755 /usr/local/bin/tree-sitter
for binary in pylsp ruff marksman tree-sitter; do
  command -v "$binary" >/dev/null || { printf '%s\n' "Outil Neovim absent après installation : $binary" >&2; exit 1; }
done
/usr/local/bin/ruff --version
/usr/local/bin/marksman --version
/usr/local/bin/tree-sitter --version

step 'Mises à jour de sécurité automatiques'
apt-get install --no-install-recommends -y $(python3 "$PAYLOAD/packages.py" --apt securite)
# Le dépôt Brave publie ses correctifs de sécurité sur l'origine « stable » ;
# l'y ajouter explicitement, sinon seules les origines Ubuntu sont couvertes.
cat > /etc/apt/apt.conf.d/52-ubunturiri-unattended <<'CONFIG'
Unattended-Upgrade::Allowed-Origins {
        "${distro_id}:${distro_codename}-security";
        "${distro_id}ESMApps:${distro_codename}-apps-security";
        "${distro_id}ESM:${distro_codename}-infra-security";
        "Brave Software:stable";
};
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
CONFIG
chmod 0644 /etc/apt/apt.conf.d/52-ubunturiri-unattended
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' \
  > /etc/apt/apt.conf.d/20auto-upgrades
chmod 0644 /etc/apt/apt.conf.d/20auto-upgrades
systemctl enable unattended-upgrades.service
unattended-upgrade --dry-run --debug >/dev/null 2>&1 \
  || printf '%s\n' 'Avertissement : la simulation unattended-upgrade a échoué dans le chroot ; à vérifier après démarrage.' >&2

step 'Navigateur Brave Origin'
install -m 0644 "$PAYLOAD/extras/brave-browser-archive-keyring.gpg" /usr/share/keyrings/brave-browser-archive-keyring.gpg
python3 "$PAYLOAD/packages.py" --brave-source > /etc/apt/sources.list.d/brave-browser.sources
chmod 0644 /etc/apt/sources.list.d/brave-browser.sources
apt-get update
apt-get install --no-install-recommends -y "$(python3 "$PAYLOAD/packages.py" --brave-package)"
# Le paquet installe le binaire sous le nom brave-origin-stable.
[[ -x /usr/bin/brave-origin-stable ]] || { printf '%s\n' 'Binaire Brave Origin absent après installation.' >&2; exit 1; }
[[ -f /usr/share/applications/brave-origin.desktop ]]

step 'Configuration de la session GNOME et du shell'
python3 "$PAYLOAD/session_setup.py" system "$USER_NAME"
python3 "$PAYLOAD/shell_setup.py" system "$USER_NAME"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
runuser -u "$USER_NAME" -- env HOME="$USER_HOME" dbus-run-session -- python3 "$PAYLOAD/session_setup.py" user
runuser -u "$USER_NAME" -- env HOME="$USER_HOME" python3 "$PAYLOAD/shell_setup.py" user
systemctl enable gdm3.service NetworkManager.service bluetooth.service
systemctl set-default graphical.target

step 'Purge du contenu embarqué'
# Tout est installé : les paquets, archives et sources embarqués ne servent
# plus. Restent nécessaires au fonctionnement les scripts Python, themes/ que
# lit theme.py à chaque ouverture de session, et files/ pour une réapplication
# du profil. Le manifeste part avec le reste, plus rien ne le vérifie.
#
# Contrepartie assumée : une réinstallation hors ligne depuis ces paquets n'est
# plus possible, il faut repartir de l'ISO.
AVANT="$(du -sm "$PAYLOAD" | cut -f1)"
rm -rf "$PAYLOAD/extras" "$PAYLOAD/pop-shell" "$PAYLOAD/icaclient.deb" "$PAYLOAD/manifest.json"
APRES="$(du -sm "$PAYLOAD" | cut -f1)"
printf 'Contenu embarqué : %s Mio → %s Mio, %s Mio rendus au disque.\n' \
  "$AVANT" "$APRES" "$((AVANT - APRES))"
for garde in theme.py citrix_mode.py session_setup.py shell_setup.py doctor.py themes files; do
  [[ -e "$PAYLOAD/$garde" ]] || { printf '%s\n' "Purge trop large : $garde manquant dans $PAYLOAD" >&2; exit 1; }
done

apt-get clean
printf '\n%s\n' 'Configuration du bureau terminée. Lancer ubunturiri-doctor après le premier démarrage pour contrôler le résultat.'
