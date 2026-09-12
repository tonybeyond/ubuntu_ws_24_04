#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from session_setup import POP_ID, POP_SCHEMA, settings

SCHEMAS = ["org.gnome.desktop.wm.keybindings", "org.gnome.shell.keybindings", "org.gnome.mutter.keybindings", POP_ID]


def snapshot():
    values = []
    for schema in SCHEMAS:
        command = ["gsettings"]
        if schema == POP_ID:
            command += ["--schemadir", POP_SCHEMA]
        keys = subprocess.check_output(command + ["list-keys", schema], text=True).splitlines()
        for key in keys:
            value = settings("get", schema, key)
            if value.startswith("[") and value != "[]":
                values.append([schema, key, value, "[]"])
    value = settings("get", "org.gnome.mutter", "overlay-key")
    values.append(["org.gnome.mutter", "overlay-key", value, "''"])
    for name in ["terminal", "theme"]:
        schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/fedoriri-" + name + "/"
        values.append([schema, "binding", settings("get", schema, "binding"), "''"])
    return values


def restore(path):
    if not path.exists():
        return False
    values = json.loads(path.read_text())
    for schema, key, before, disabled in values:
        settings("set", schema, key, before)
    path.unlink()
    return True


def activate(path):
    values = snapshot()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(values))
    temporary.chmod(0o600)
    temporary.replace(path)
    try:
        for schema, key, before, disabled in values:
            settings("set", schema, key, disabled)
    except subprocess.CalledProcessError:
        restore(path)
        raise


def main():
    parser = argparse.ArgumentParser(description="Basculer les raccourcis GNOME/Pop Shell pour Citrix. Super+Échap les rétablit ; le verrouillage local reste disponible.")
    parser._option_string_actions["--help"].help = "afficher cette aide et quitter"
    parser.add_argument("--restore", action="store_true", help="restaurer les raccourcis sauvegardés, notamment à la connexion")
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise ValueError("Exécuter dans la session GNOME utilisateur, pas avec sudo.")
    os.umask(0o077)
    path = Path.home() / ".local/state/fedoriri/citrix-mode.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists() or args.restore:
            changed = restore(path)
            message = "Raccourcis locaux rétablis."
        else:
            activate(path)
            changed = True
            message = "Mode Citrix : raccourcis GNOME/Pop Shell suspendus. Super+Échap pour revenir ; Super+L verrouille toujours le poste."
    if changed:
        print(message)
        subprocess.run(["notify-send", "Citrix", message], check=False)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Mode Citrix en échec : {error}", file=sys.stderr)
        sys.exit(1)
