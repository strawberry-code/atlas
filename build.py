#!/usr/bin/env python3
"""Impacchetta payload/ dentro dist/atlas-install.py.

Il payload viaggia come tar.gz codificato base64 dentro il sorgente dell'installer,
cosi' resta un file solo da copiare e non serve rete per installarlo.
"""
from __future__ import annotations

import base64
import io
import tarfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "payload"
USCITA = ROOT / "dist" / "atlas-install.py"


def normalizza(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Archivio riproducibile: niente owner, niente mtime, permessi prevedibili."""
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.isdir() or info.name.endswith("bin/atlas") else 0o644
    return info


def impacchetta() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", compresslevel=9) as tf:
        for path in sorted(PAYLOAD.rglob("*")):
            if "__pycache__" in path.parts or path.name == ".DS_Store":
                continue
            tf.add(path, arcname=str(path.relative_to(PAYLOAD)), filter=normalizza)
    return buffer.getvalue()


def main() -> int:
    versione = (PAYLOAD / "VERSION").read_text(encoding="utf-8").strip()
    blob = base64.b64encode(impacchetta()).decode("ascii")
    sorgente = (ROOT / "installer_template.py").read_text(encoding="utf-8")
    sorgente = sorgente.replace("__VERSION__", versione)
    sorgente = sorgente.replace("__PAYLOAD__", "\n" + "\n".join(textwrap.wrap(blob, 96)) + "\n")
    USCITA.parent.mkdir(exist_ok=True)
    USCITA.write_text(sorgente, encoding="utf-8")
    USCITA.chmod(0o755)
    print(f"  {USCITA.relative_to(ROOT)} · {USCITA.stat().st_size / 1024:.1f} KB · versione {versione}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
