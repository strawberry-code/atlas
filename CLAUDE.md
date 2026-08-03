# CLAUDE.md — Atlas

Harness di task a grafo, distribuito come CLI globale installabile via curl. Qui si sviluppa Atlas; il modo di lavorare che Atlas impone ai progetti ospiti sta in `payload/templates/contract.md`. Licenza: AGPL-3.0 (`LICENSE`).

## Struttura

- `payload/` è l'unica cosa che finisce dentro un progetto ospite (l'harness in `.atlas/`). Tutto ciò che sta qui deve funzionare con la sola stdlib di Python 3.10, su POSIX, senza rete.
- `atlascli/` è il CLI globale (`atlas`): install/update/uninstall/list, il registro dei progetti (`~/.atlas/registry.json`), il self-update. Anche qui solo stdlib — niente pip — ma la rete verso GitHub è consentita: è un prodotto diverso da `payload/`, con un vincolo diverso. `atlascli/dispatch.py` decide, in quest'ordine, se un comando è riservato (install/update/uninstall/list), lo slug di un progetto registrato, o va passato com'è al motore locale del progetto corrente (`os.execv` su `payload/bin/atlas`, invariato).
- `build.py` impacchetta `payload/` come tar.gz+base64 dentro `atlascli/_payload.py` (generato, gitignored, mai committato), poi impacchetta `atlascli/` intero con `zipapp` della stdlib in `dist/atlas` — un solo eseguibile. `dist/atlas` è un deliverable **binario** (blob zip): tracciato in git ma non diffabile riga per riga: il review passa dai sorgenti in `atlascli/*.py` e `payload/*`, non dal diff di `dist/`.
- `install.sh` è lo script POSIX per `curl | sh`: scarica `dist/atlas` dall'ultima release GitHub e lo mette su `~/.local/bin`.
- `release.py` è il runbook di release, invocato a mano: bump versione, build, test, sha256. Non tagga né pusha da solo — quei comandi restano manuali.
- `tests/` usa `unittest` della stdlib. Nessun runner esterno. `tests/httpfixture.py` è un server HTTP fittizio locale (stdlib `http.server`), usato per testare self-update e `install.sh` senza rete vera.

## Regole

- **Zero dipendenze in `payload/` e in `atlascli/`.** Un import di terze parti in uno dei due rompe la promessa dell'eseguibile singolo. Nei test e in `build.py`/`release.py` vale la stessa regola, per non dover installare niente prima di poter costruire.
- **La rete è vietata solo in `payload/`.** `atlascli/self_update.py` e `install.sh` parlano con l'API di GitHub (`urllib` della stdlib) — è l'unica eccezione dichiarata al vincolo "senza rete", e vale solo per il layer che gestisce i progetti, mai per il motore che ci finisce dentro.
- **Dopo ogni modifica a `payload/` o `atlascli/` va rigenerato il CLI** con `python3 build.py`, altrimenti `dist/atlas` mente.
- I file di `payload/core/` stanno sotto le 200 righe. Il rimedio al superamento è spezzare, non comprimere: un file che sfora di solito sta facendo due lavori. Stessa disciplina, dove ragionevole, per `atlascli/*.py`.
- **Eccezione dichiarata: `core/cli.py`.** Un dispatcher di comandi cresce in larghezza, non in profondità, e spezzarlo produrrebbe moduli che esistono solo per rispettare un numero. La sua parte stampabile è già uscita in `report.py`, e le mutazioni non ci passano affatto. Resta un file solo finché resta un dispatcher: se ci finisce dentro della logica che non sia parsing e smistamento, quella va altrove.
- La prosa dei documenti generati (ticket, `map.md`, dashboard) è in italiano, con gli accenti scritti alla fonte. Il codice e i nomi dei simboli in inglese.

## Verifica

```bash
python3 -m unittest discover -s tests
python3 build.py && python3 tests/e2e.py    # installa in una sandbox e ne verifica il ciclo
```
