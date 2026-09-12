#!/usr/bin/env bash
set +x
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export PYTHONDONTWRITEBYTECODE=1
USER_NAME="${1:?Nom utilisateur requis}"
PAYLOAD=/opt/ubunturiri
[[ "$EUID" -eq 0 ]] || { printf '%s\n' 'Exécuter dans la cible Ubuntu avec les droits administrateur.' >&2; exit 1; }
python3 "$PAYLOAD/iso_config.py" verify-payload "$PAYLOAD"
chmod -R a+rX "$PAYLOAD"
python3 -c 'import platform; r=platform.freedesktop_os_release(); assert r.get("ID")=="ubuntu" and r.get("VERSION_ID")=="24.04", "Ubuntu 24.04 requis"'
[[ "$(dpkg --print-architecture)" == amd64 ]] || { printf '%s\n' 'Cible AMD64 requise pour Citrix.' >&2; exit 1; }
id "$USER_NAME" >/dev/null
printf '%s\n' 'Installation du bureau minimal et des dépendances Citrix depuis Ubuntu 24.04.'
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
printf '%s\n' 'Compilation de Pop Shell pour GNOME 46, sans lancer ni redémarrer GNOME dans le chroot.'
POP_BUILD="$(mktemp -d /tmp/ubunturiri-pop.XXXXXX)"
trap 'rm -rf -- "$POP_BUILD"' EXIT
cp -a "$PAYLOAD/pop-shell/." "$POP_BUILD/"
make -C "$POP_BUILD" all
make -C "$POP_BUILD" DESTDIR=/ install
[[ -f /usr/share/gnome-shell/extensions/pop-shell@system76.com/metadata.json ]]
printf '%s\n' 'Bureautique LibreOffice et dictionnaires français.'
apt-get install --no-install-recommends -y $(python3 "$PAYLOAD/packages.py" --apt libreoffice)
[[ -x /usr/bin/libreoffice ]]

printf '%s\n' 'Outils en ligne de commande.'
apt-get install --no-install-recommends -y $(python3 "$PAYLOAD/packages.py" --apt shell)
for binary in eza zoxide fzf rg fdfind batcat jq tmux aria2c; do
  command -v "$binary" >/dev/null || { printf '%s\n' "Binaire attendu absent après installation : $binary" >&2; exit 1; }
done

printf '%s\n' 'Paquets DEB embarqués : Ghostty, NetBird, fastfetch.'
apt-get install --no-install-recommends -y \
  "$PAYLOAD/extras/ghostty.deb" \
  "$PAYLOAD/extras/netbird.deb" \
  "$PAYLOAD/extras/netbird-ui.deb" \
  "$PAYLOAD/extras/fastfetch.deb"
for package in ghostty netbird netbird-ui fastfetch; do
  [[ "$(dpkg-query -W -f='${Status}' "$package")" == 'install ok installed' ]] || { printf '%s\n' "Paquet non installé : $package" >&2; exit 1; }
done
for binary in /usr/bin/ghostty /usr/bin/netbird /usr/bin/fastfetch; do
  if ldd "$binary" | grep -q 'not found'; then
    printf '%s\n' "Bibliothèques manquantes pour $binary : installation arrêtée." >&2
    exit 1
  fi
done
# Le service netbird est activé mais le poste n'est enrôlé dans aucun réseau :
# lancer netbird up --setup-key après le premier démarrage.
systemctl enable netbird.service

printf '%s\n' 'Neovim 0.12 depuis l’archive amont épinglée.'
rm -rf /opt/nvim
mkdir -p /opt/nvim
tar -xzf "$PAYLOAD/extras/nvim.tar.gz" -C /opt/nvim --strip-components=1
[[ -x /opt/nvim/bin/nvim ]]
ln -sfn /opt/nvim/bin/nvim /usr/local/bin/nvim
/usr/local/bin/nvim --version | head -n1
update-alternatives --install /usr/bin/editor editor /opt/nvim/bin/nvim 60

printf '%s\n' 'Starship et ble.sh.'
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

printf '%s\n' 'Police JetBrainsMono Nerd Font.'
FONT_DIR=/usr/local/share/fonts/JetBrainsMonoNerdFont
rm -rf "$FONT_DIR"
mkdir -p "$FONT_DIR"
# Seule la variante Mono est retenue : chasse fixe pour les glyphes, et
# l'archive complète pèse 79 Mio contre 39 Mio pour cette variante seule.
tar -xJf "$PAYLOAD/extras/jetbrains-mono-nerd-font.tar.xz" -C "$FONT_DIR" \
  --wildcards 'JetBrainsMonoNerdFontMono-*.ttf' 'OFL.txt'
chmod -R a+rX "$FONT_DIR"
fc-cache -f "$FONT_DIR" >/dev/null
fc-list | grep -q 'JetBrainsMono Nerd Font Mono' || { printf '%s\n' 'Police Nerd Font non enregistrée par fontconfig.' >&2; exit 1; }

printf '%s\n' 'Navigateur Brave Origin depuis le dépôt officiel Brave.'
install -m 0644 "$PAYLOAD/extras/brave-browser-archive-keyring.gpg" /usr/share/keyrings/brave-browser-archive-keyring.gpg
python3 "$PAYLOAD/packages.py" --brave-source > /etc/apt/sources.list.d/brave-browser.sources
chmod 0644 /etc/apt/sources.list.d/brave-browser.sources
apt-get update
apt-get install --no-install-recommends -y "$(python3 "$PAYLOAD/packages.py" --brave-package)"
# Le paquet installe le binaire sous le nom brave-origin-stable.
[[ -x /usr/bin/brave-origin-stable ]] || { printf '%s\n' 'Binaire Brave Origin absent après installation.' >&2; exit 1; }
[[ -f /usr/share/applications/brave-origin.desktop ]]

python3 "$PAYLOAD/session_setup.py" system "$USER_NAME"
python3 "$PAYLOAD/shell_setup.py" system "$USER_NAME"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
runuser -u "$USER_NAME" -- env HOME="$USER_HOME" dbus-run-session -- python3 "$PAYLOAD/session_setup.py" user
runuser -u "$USER_NAME" -- env HOME="$USER_HOME" python3 "$PAYLOAD/shell_setup.py" user
systemctl enable gdm3.service NetworkManager.service bluetooth.service
systemctl set-default graphical.target
apt-get clean
printf '%s\n' 'Configuration du bureau terminée. GNOME X11 et Citrix restent à valider après démarrage.'
