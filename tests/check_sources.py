import argparse
import contextlib
import io
import json
import lzma
import re
import shlex
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_iso
import session_setup
import theme


def main():
    parser = argparse.ArgumentParser(description="Contrôler les archives et index Ubuntu déjà téléchargés.", add_help=False)
    parser.add_argument("-h", "--help", action="help", help="afficher cette aide et quitter")
    parser.add_argument("directory", type=Path, metavar="DOSSIER")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name in ["pop-shell", "fedoriri"]:
            (root / name).mkdir()
        pop = build_iso.unpack(args.directory / "pop-shell.tar.gz", root / "pop-shell")
        upstream = build_iso.unpack(args.directory / "fedoriri.tar.gz", root / "fedoriri")
        assert "46" in json.loads((pop / "metadata.json").read_text())["shell-version"]
        assert (upstream / "LICENSE").is_file()
        keys = {key.attrib["name"] for key in ET.parse(pop / "schemas/org.gnome.shell.extensions.pop-shell.gschema.xml").iter("key")}
        def setting(action, schema, key, value=None):
            if schema == session_setup.POP_ID:
                assert key in keys, f"Clé Pop Shell inconnue : {key}"
            return "@as []" if action == "get" else ""
        with patch("session_setup.os.geteuid", return_value=1000), patch("session_setup.Path.home", return_value=root), patch("session_setup.settings", side_effect=setting), patch("session_setup.subprocess.run"):
            session_setup.configure_user()
        print("Archives épinglées, licence Fedoriri et clés Pop Shell/GNOME 46 contrôlées.")
        palettes = sorted((upstream / "desktop/themes").glob("*/colors.toml"))
        assert palettes
        def themed_setting(action, schema, key, value=None):
            if action == "get":
                return "'b1dcc9dd-5262-4d8d-a863-c897e6d979b9'"
            if schema == session_setup.POP_ID:
                assert key in keys
            return ""
        with patch("theme.THEMES", upstream / "desktop/themes"), patch("theme.Path.home", return_value=root), patch("theme.settings", side_effect=themed_setting), contextlib.redirect_stdout(io.StringIO()):
            for colors in palettes:
                theme.apply_theme(colors.parent.name)
        print(f"Palettes réelles rendues avec appels GNOME simulés : {len(palettes)}.")
    packages = set()
    for component in ["main", "universe"]:
        with lzma.open(args.directory / f"{component}.xz", "rt") as stream:
            for line in stream:
                if line.startswith("Package: "):
                    packages.add(line.split(": ", 1)[1].strip())
    script = (build_iso.ROOT / "scripts/install-desktop.sh").read_text()
    block = script.split("apt-get install --no-install-recommends -y \\\n", 1)[1].split("\napt-get install", 1)[0]
    names = shlex.split(block.replace("\\\n", " "))
    missing = sorted(set(names) - packages)
    assert not missing, f"Paquets absents de Noble AMD64 : {missing}"
    print(f"Noms de paquets présents dans les index Noble AMD64 : {len(names)}. Résolution APT et installation non testées.")


if __name__ == "__main__":
    main()
