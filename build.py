#!/usr/bin/env python3
"""Impacchetta i due deliverable di Atlas: dist/atlas (CLI globale) e il suo sha256.

Il payload (payload/, il motore per-progetto) viaggia come tar.gz+base64 imbustato
dentro atlascli/_payload.py: quel file e' generato qui, mai scritto a mano, mai
committato (vedi .gitignore). atlascli/ intero viene poi impacchettato con lo
zipapp della stdlib in un solo eseguibile: nessuna dipendenza esterna, nessun passo
di build oltre a 'python3 build.py'.
"""
from __future__ import annotations

import base64
import hashlib
import io
import shutil
import tarfile
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAYLOAD_DIR = ROOT / "payload"
ATLASCLI_DIR = ROOT / "atlascli"
PAYLOAD_MODULE = ATLASCLI_DIR / "_payload.py"
DIST = ROOT / "dist"
CLI_OUT = DIST / "atlas"
CLI_SHA = DIST / "atlas.sha256"


def _normalizza(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Archivio riproducibile: niente owner, niente mtime, permessi prevedibili."""
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.isdir() or info.name.endswith("bin/atlas") else 0o644
    return info


def valida_coppie_lingua() -> None:
    """Ogni template e ogni skill deve avere sia .it. sia .en.: mancarne una non fa
    esplodere subito il build, ma scompatta() con un FileNotFoundError a runtime,
    solo per chi sceglie la lingua mancante. Meglio fermarsi qui.
    """
    mancanti: set[str] = set()

    template_dir = PAYLOAD_DIR / "templates"
    for path in sorted(template_dir.iterdir()):
        for lingua, altra in (("it", "en"), ("en", "it")):
            marcatore = f".{lingua}."
            if marcatore in path.name:
                gemello = template_dir / path.name.replace(marcatore, f".{altra}.", 1)
                if not gemello.is_file():
                    mancanti.add(str(gemello.relative_to(PAYLOAD_DIR)))

    for skill_dir in sorted((PAYLOAD_DIR / "skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        for lingua, altra in (("it", "en"), ("en", "it")):
            atteso, gemello = skill_dir / f"SKILL.{lingua}.md", skill_dir / f"SKILL.{altra}.md"
            if atteso.is_file() and not gemello.is_file():
                mancanti.add(str(gemello.relative_to(PAYLOAD_DIR)))

    if mancanti:
        elenco = "\n".join(f"    {m}" for m in sorted(mancanti))
        raise SystemExit(f"  Traduzioni mancanti, build interrotta:\n{elenco}\n")


def pack_payload() -> tuple[str, str]:
    """Ritorna (versione, blob base64) del motore in payload/."""
    versione = (PAYLOAD_DIR / "VERSION").read_text(encoding="utf-8").strip()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", compresslevel=9) as tf:
        for path in sorted(PAYLOAD_DIR.rglob("*")):
            if "__pycache__" in path.parts or path.name == ".DS_Store":
                continue
            tf.add(path, arcname=str(path.relative_to(PAYLOAD_DIR)), filter=_normalizza)
    return versione, base64.b64encode(buffer.getvalue()).decode("ascii")


def build_cli() -> None:
    """zipapp appiattisce la cartella sorgente alla radice dello zip: se ci puntassimo
    direttamente ATLASCLI_DIR, 'atlascli' smetterebbe di esistere come package dentro
    l'archivio e le sue import relative ('from . import registry') si romperebbero.
    Si zippa invece una cartella di staging che contiene 'atlascli/' come sottocartella,
    cosi' il package resta un package anche impacchettato.
    """
    valida_coppie_lingua()
    versione, blob = pack_payload()
    PAYLOAD_MODULE.write_text(
        f'"""Generato da build.py: NON modificare a mano, NON committare."""\n'
        f'VERSION = "{versione}"\n'
        f'PAYLOAD_B64 = "{blob}"\n',
        encoding="utf-8",
    )
    try:
        DIST.mkdir(exist_ok=True)
        ignora = shutil.ignore_patterns("__pycache__", ".DS_Store")
        with tempfile.TemporaryDirectory() as staging:
            shutil.copytree(ATLASCLI_DIR, Path(staging) / "atlascli", ignore=ignora)
            zipapp.create_archive(staging, CLI_OUT, interpreter="/usr/bin/env python3",
                                   main="atlascli.main:run")
        CLI_OUT.chmod(0o755)
        CLI_SHA.write_text(f"{hashlib.sha256(CLI_OUT.read_bytes()).hexdigest()}  atlas\n", encoding="utf-8")
    finally:
        PAYLOAD_MODULE.unlink(missing_ok=True)
    print(f"  {CLI_OUT.relative_to(ROOT)} · {CLI_OUT.stat().st_size / 1024:.1f} KB · versione {versione}")
    print(f"  {CLI_SHA.relative_to(ROOT)}")


def main() -> int:
    build_cli()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
