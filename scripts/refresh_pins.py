#!/usr/bin/env python3
"""Recalcule les empreintes SHA-256 de packages.py après un changement de version.

Sans --write : télécharge chaque URL et signale les écarts, sans rien modifier.
Avec --write : réécrit les champs sha256 de scripts/packages.py.

Procédure de montée de version :
  1. changer url et version dans PINS ;
  2. python3 scripts/refresh_pins.py --write ;
  3. relire le diff de packages.py avant de committer.
"""
import argparse
import hashlib
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from packages import PINS

SOURCE = Path(__file__).resolve().parent / "packages.py"


def digest(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ubunturiri-ISO/1", "Accept-Encoding": "identity"})
    checksum = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=120) as source:
        if not source.geturl().startswith("https://"):
            raise ValueError("Téléchargement non HTTPS refusé.")
        while chunk := source.read(1024 ** 2):
            checksum.update(chunk)
            size += len(chunk)
    return checksum.hexdigest(), size


def main():
    parser = argparse.ArgumentParser(description="Recalculer les empreintes des composants épinglés.")
    parser.add_argument("--write", action="store_true", help="réécrire scripts/packages.py au lieu de seulement signaler")
    args = parser.parse_args()
    text = SOURCE.read_text()
    changed = 0
    for name, pin in PINS.items():
        actual, size = digest(pin["url"])
        state = "inchangé" if actual == pin["sha256"] else "DIFFÉRENT"
        print(f"{name:52} {pin['version']:16} {size / 1024 ** 2:7.1f} Mio  {state}")
        if actual != pin["sha256"]:
            changed += 1
            if args.write:
                old = f'"sha256": "{pin["sha256"]}"'
                if text.count(old) != 1:
                    raise ValueError(f"Empreinte non unique dans packages.py pour {name}.")
                text = text.replace(old, f'"sha256": "{actual}"')
    if args.write and changed:
        SOURCE.write_text(text)
        print(f"{changed} empreinte(s) réécrite(s) dans {SOURCE}.")
    elif changed:
        print(f"{changed} écart(s) ; relancer avec --write pour les appliquer.", file=sys.stderr)
        return 1
    else:
        print("Toutes les empreintes correspondent.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        sys.exit(1)
