#!/usr/bin/env python3
import ast
import configparser
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path

PAYLOAD = Path("/opt/fedoriri")
POP_SCHEMA = "/usr/share/gnome-shell/extensions/pop-shell@system76.com/schemas"
POP_ID = "org.gnome.shell.extensions.pop-shell"


def settings(action, schema, key, value=None):
    args = ["gsettings"]
    if schema == POP_ID:
        args += ["--schemadir", POP_SCHEMA]
    args += [action, schema, key]
    if value is not None:
        args.append(value)
    return subprocess.check_output(args, text=True).strip()


def write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def system(username):
    if os.geteuid() != 0:
        raise ValueError("Configuration système réservée à l’installation.")
    pwd.getpwnam(username)
    if not Path("/usr/share/xsessions/gnome-xorg.desktop").is_file():
        raise ValueError("La session GNOME Xorg n’est pas installée.")
    path = Path("/etc/gdm3/custom.conf")
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(path)
    if not config.has_section("daemon"):
        config.add_section("daemon")
    config["daemon"]["WaylandEnable"] = "false"
    config["daemon"]["DefaultSession"] = "gnome-xorg.desktop"
    config["daemon"]["AutomaticLoginEnable"] = "false"
    with path.open("w") as stream:
        config.write(stream)
    write(Path("/var/lib/AccountsService/users") / username, "[User]\nSession=gnome-xorg\nXSession=gnome-xorg\nSystemAccount=false\n", 0o600)
    write(Path("/etc/netplan/99-fedoriri-renderer.yaml"), "network:\n  version: 2\n  renderer: NetworkManager\n", 0o600)
    for command, script in [("fedoriri-theme-set", "theme.py"), ("fedoriri-citrix-mode", "citrix_mode.py")]:
        target = Path("/usr/local/bin") / command
        target.unlink(missing_ok=True)
        (PAYLOAD / script).chmod(0o755)
        target.symlink_to(PAYLOAD / script)
    write(Path("/etc/xdg/autostart/fedoriri-session.desktop"), "[Desktop Entry]\nType=Application\nName=Initialisation Fedoriri\nExec=python3 /opt/fedoriri/session_setup.py login\nOnlyShowIn=GNOME;\nX-GNOME-Autostart-enabled=true\n")


def configure_user():
    if os.geteuid() == 0:
        raise ValueError("Configurer la session avec le compte utilisateur, pas root.")
    home = Path.home()
    values = {
        "org.gnome.desktop.input-sources": {"sources": "[('xkb', 'ch+fr')]"},
        "org.gnome.desktop.interface": {"color-scheme": "'prefer-dark'", "monospace-font-name": "'Fira Code 11'"},
        "org.gnome.desktop.session": {"idle-delay": "uint32 600"},
        "org.gnome.desktop.screensaver": {"lock-enabled": "true"},
        "org.gnome.mutter": {"workspaces-only-on-primary": "false"},
        "org.gnome.shell": {"disable-user-extensions": "false"},
        POP_ID: {"tile-by-default": "true", "active-hint": "true", "gap-inner": "uint32 4", "gap-outer": "uint32 4", "tile-enter": "['<Super>r']", "activate-launcher": "[]"},
    }
    for schema, mapping in values.items():
        for key, value in mapping.items():
            settings("set", schema, key, value)
    enabled = settings("get", "org.gnome.shell", "enabled-extensions")
    extensions = [] if enabled.startswith("@as") else ast.literal_eval(enabled)
    for uuid in ["pop-shell@system76.com", "ubuntu-appindicators@ubuntu.com"]:
        if Path("/usr/share/gnome-shell/extensions", uuid).is_dir() and uuid not in extensions:
            extensions.append(uuid)
    settings("set", "org.gnome.shell", "enabled-extensions", repr(extensions))
    for key in ["minimize", "maximize", "unmaximize", "switch-to-workspace-left", "switch-to-workspace-right", "move-to-monitor-left", "move-to-monitor-right", "move-to-monitor-up", "move-to-monitor-down", "move-to-workspace-up", "move-to-workspace-down"]:
        settings("set", "org.gnome.desktop.wm.keybindings", key, "[]")
    for key in ["toggle-tiled-left", "toggle-tiled-right"]:
        settings("set", "org.gnome.mutter.keybindings", key, "[]")
    settings("set", "org.gnome.shell.keybindings", "toggle-overview", "['<Super>space']")
    media = "org.gnome.settings-daemon.plugins.media-keys"
    raw = settings("get", media, "custom-keybindings")
    paths = [] if raw.startswith("@as") else ast.literal_eval(raw)
    shortcuts = [("terminal", "Terminal", "gnome-terminal", "<Super>Return"), ("citrix", "Mode clavier Citrix", "fedoriri-citrix-mode", "<Super>Escape"), ("theme", "Thème suivant", "fedoriri-theme-set --next", "<Super><Shift>y")]
    for name, label, command, binding in shortcuts:
        path = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/fedoriri-{name}/"
        if path not in paths:
            paths.append(path)
        schema = media + ".custom-keybinding:" + path
        for key, value in {"name": label, "command": command, "binding": binding}.items():
            settings("set", schema, key, repr(value))
    settings("set", media, "custom-keybindings", repr(paths))
    config = home / ".config/pop-shell/config.json"
    data = json.loads(config.read_text()) if config.exists() else {"float": []}
    rule = {"class": "^(wfica|Wfica_Seamless|Wfica_FullScreen|Citrix Workspace)$"}
    if rule not in data.setdefault("float", []):
        data["float"].append(rule)
    write(config, json.dumps(data, indent=2) + "\n", 0o600)
    citrix = home / ".ICAClient/wfclient.ini"
    if not citrix.exists():
        write(citrix, "[WFClient]\nVersion=2\nKeyboardLayout=(User Profile)\n", 0o600)
    subprocess.run([sys.executable, str(PAYLOAD / "theme.py"), "tokyo-night"], check=True)
    write(home / ".local/state/fedoriri/configured", "1\n", 0o600)


def main():
    if len(sys.argv) < 2:
        raise ValueError("Usage : session_setup.py system UTILISATEUR | user | login")
    action = sys.argv[1]
    if action == "system" and len(sys.argv) == 3:
        system(sys.argv[2])
    elif action == "user":
        configure_user()
    elif action == "login":
        if os.environ.get("XDG_SESSION_TYPE") != "x11":
            raise ValueError("Session X11 requise pour ce profil Citrix.")
        subprocess.run([sys.executable, str(PAYLOAD / "citrix_mode.py"), "--restore"], check=True)
        if not (Path.home() / ".local/state/fedoriri/configured").exists():
            configure_user()
    else:
        raise ValueError("Action inconnue.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Configuration de session arrêtée : {error}", file=sys.stderr)
        sys.exit(1)
