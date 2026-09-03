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
import json
import shutil
import sys
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
    info.mode = 0o755 if info.isdir() or info.name == "atlas" else 0o644
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


# Quel che va scritto dentro un progetto ospite. Solo le skill: sono file veri
# perche' Claude Code le legge da .claude/skills/ via symlink, e un package Python
# non le raggiungerebbe. Tutto il resto del motore viaggia importabile nel CLI.
DA_INSTALLARE = ("skills",)


def pack_payload() -> tuple[str, str]:
    """Ritorna (versione, blob base64) di quel che si scrive dentro .atlas/."""
    versione = (PAYLOAD_DIR / "VERSION").read_text(encoding="utf-8").strip()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", compresslevel=9) as tf:
        for voce in DA_INSTALLARE:
            for path in sorted((PAYLOAD_DIR / voce).rglob("*")):
                if "__pycache__" in path.parts or path.name == ".DS_Store":
                    continue
                # recursive=False, altrimenti aggiungere una cartella ci infila dentro
                # tutto il suo contenuto e il filtro qui sopra non lo vede mai: rglob
                # enumera gia' ogni file, e senza questo il bytecode finiva spedito.
                tf.add(path, arcname=str(path.relative_to(PAYLOAD_DIR)),
                       filter=_normalizza, recursive=False)
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
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            shutil.copytree(ATLASCLI_DIR, staging / "atlascli", ignore=ignora)
            # Il motore entra nello stesso archivio come package importabile: e' quel
            # che permette a un solo comando di essere insieme gestore e motore, e agli
            # script di mutazione di scrivere 'from core import mutate' senza che nel
            # progetto ci sia una riga di codice.
            shutil.copytree(PAYLOAD_DIR / "core", staging / "core", ignore=ignora)
            # I template diventano risorse del package: dentro uno zip non si aprono
            # con Path, e core/risorse.py li legge con importlib.resources.
            shutil.copytree(PAYLOAD_DIR / "templates", staging / "core" / "templates",
                            ignore=ignora)
            (staging / "core" / "templates" / "__init__.py").write_text(
                '"""I template del motore, letti da core/risorse.py."""\n', encoding="utf-8")
            zipapp.create_archive(staging, CLI_OUT, interpreter="/usr/bin/env python3",
                                   main="atlascli.main:run")
        CLI_OUT.chmod(0o755)
        CLI_SHA.write_text(f"{hashlib.sha256(CLI_OUT.read_bytes()).hexdigest()}  atlas\n", encoding="utf-8")
    finally:
        PAYLOAD_MODULE.unlink(missing_ok=True)
    print(f"  {CLI_OUT.relative_to(ROOT)} · {CLI_OUT.stat().st_size / 1024:.1f} KB · versione {versione}")
    print(f"  {CLI_SHA.relative_to(ROOT)}")


# Stati di run-state.json che descrivono un run ancora in piedi. Gli altri
# ('completed', 'failed', 'blocked') descrivono un run finito, che non sta piu'
# eseguendo l'archivio.
RUN_VIVI = {"active", "waiting"}


def run_in_corso() -> list[str]:
    """I grafi di questo repo con un run non ancora concluso.

    'dist/atlas' e' uno zipapp, e zipimport tiene gli offset del file aperto
    all'avvio: sovrascriverlo mentre un run lo sta eseguendo non si nota subito,
    perche' quel che e' gia' in memoria continua a funzionare, e poi il primo
    import differito muore con 'bad local file header'. E' lo stesso guasto che
    il contratto descrive per 'atlas update', vissuto dall'altro lato. E' gia'
    successo: un nodo lavorato da Autopilot ha rifatto la build mentre il pilota
    ci girava sopra, ed e' sopravvissuto per fortuna, non per costruzione.
    """
    graphs = ROOT / ".atlas" / "graphs"
    if not graphs.is_dir():
        return []
    vivi = []
    for stato in sorted(graphs.glob("*/run-state.json")):
        try:
            dati = json.loads(stato.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Un ledger illeggibile non e' una prova che un run stia girando, e
            # bloccare la build su un file corrotto sarebbe peggio del rischio.
            continue
        if dati.get("status") in RUN_VIVI:
            vivi.append(stato.parent.name)
    return vivi


def main(argv: list[str] | None = None) -> int:
    argomenti = list(sys.argv[1:] if argv is None else argv)
    forza = "--force" in argomenti
    if not forza and (vivi := run_in_corso()):
        print(f"  run in corso su {', '.join(vivi)}: build annullata.")
        print("  Sostituire dist/atlas mentre un run lo esegue lo fa morire piu' tardi,")
        print("  su un import differito, con un errore che non nomina la causa.")
        print("  Aspetta la fine del run, oppure forza con --force se sai cosa stai facendo.")
        return 1
    build_cli()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
