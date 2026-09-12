#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True
from session_setup import POP_ID, settings

THEMES = Path("/opt/ubunturiri/themes")


def palette(path):
    with path.open("rb") as stream:
        colors = tomllib.load(stream)
    for key in ["background", "foreground", "accent"]:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", colors.get(key, "")):
            raise ValueError(f"Couleur requise invalide : {key}")
    return colors


def apply_theme(name):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
        raise ValueError("Nom de thème invalide.")
    colors = palette(THEMES / name / "colors.toml")
    light = colors.get("mode") == "light"
    settings("set", "org.gnome.desktop.interface", "color-scheme", repr("prefer-light" if light else "prefer-dark"))
    settings("set", "org.gnome.desktop.interface", "gtk-theme", repr("Adwaita" if light else "Adwaita-dark"))
    for key in ["primary-color", "secondary-color"]:
        settings("set", "org.gnome.desktop.background", key, repr(colors["background"]))
    for key in ["picture-uri", "picture-uri-dark"]:
        settings("set", "org.gnome.desktop.background", key, "''")
    settings("set", "org.gnome.desktop.background", "color-shading-type", "'solid'")
    settings("set", POP_ID, "hint-color-rgba", repr(colors["accent"]))
    profile = settings("get", "org.gnome.Terminal.ProfilesList", "default").strip("'")
    if not re.fullmatch(r"[a-fA-F0-9-]{36}", profile):
        raise ValueError("Profil de terminal GNOME introuvable.")
    schema = f"org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:{profile}/"
    settings("set", schema, "use-theme-colors", "false")
    for key in ["background", "foreground"]:
        settings("set", schema, key + "-color", repr(colors[key]))
    order = ["background", "red", "green", "yellow", "blue", "magenta", "cyan", "foreground"]
    normal = [colors.get(key, colors["foreground"]) for key in order]
    bright = [colors.get("bright_" + key, normal[index]) for index, key in enumerate(order)]
    settings("set", schema, "palette", repr(normal + bright))
    state = Path.home() / ".local/state/ubunturiri/theme"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(name + "\n")
    print(f"Palette appliquée au fond, au terminal et à Pop Shell : {name}")


def main():
    parser = argparse.ArgumentParser(description="Changer les palettes ubunturiri adaptées à GNOME.")
    parser._option_string_actions["--help"].help = "afficher cette aide et quitter"
    parser._positionals.title = "arguments"
    parser.add_argument("name", nargs="?", metavar="THÈME")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="afficher les thèmes disponibles")
    group.add_argument("--next", action="store_true", help="appliquer le thème suivant")
    args = parser.parse_args()
    names = sorted(path.parent.name for path in THEMES.glob("*/colors.toml"))
    if args.list:
        print("\n".join(names))
        return
    if os.geteuid() == 0:
        raise ValueError("Appliquer le thème dans la session utilisateur, pas avec sudo.")
    if args.next:
        if not names:
            raise ValueError("Aucun thème installé.")
        state = Path.home() / ".local/state/ubunturiri/theme"
        current = state.read_text().strip() if state.exists() else ""
        name = names[(names.index(current) + 1) % len(names)] if current in names else names[0]
    else:
        name = args.name or "tokyo-night"
    if name not in names:
        raise ValueError("Thème inconnu ; utiliser --list.")
    apply_theme(name)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Thème non appliqué : {error}", file=sys.stderr)
        sys.exit(1)
