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
  git build-essential node-typescript btop bash-completion unzip python3
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
python3 "$PAYLOAD/session_setup.py" system "$USER_NAME"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
runuser -u "$USER_NAME" -- env HOME="$USER_HOME" dbus-run-session -- python3 "$PAYLOAD/session_setup.py" user
systemctl enable gdm3.service NetworkManager.service bluetooth.service
systemctl set-default graphical.target
apt-get clean
printf '%s\n' 'Configuration du bureau terminée. GNOME X11 et Citrix restent à valider après démarrage.'
