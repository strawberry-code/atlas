# L02 · Da liveness a lease: il modello

> Nodo di grilling del grafo `260825-sync-distribuita` (ramo "Lucchetto fra macchine").
> Decisione presa in autonomia (AFK), interrogando il codice e i numeri veri di L01.
> Questa nota è la versione estesa; la Risposta del ticket `L02.md` è il vincolo operativo per L04 e L05.

## Il problema in una riga

Oggi un claim vale finché il suo PID esiste su questa macchina; quando il holder sta su un'altra macchina il PID non è verificabile, quindi la liveness deve diventare un **lease a tempo**: il claim porta una scadenza assoluta, e un lettore remoto la giudica col proprio orologio.

## Stato attuale (interrogato sul codice)

- `claims.py::claim` scrive `claim = {pid, session, identity, at, heartbeat, fingerprint}`. L'heartbeat si rinnova solo su `claim` di un nodo proprio.
- `claims.py::claim_state` è `dead` se `not alive(pid, process_name)`, `idle` se l'heartbeat è più vecchio di `idle_hours` (4 h), `live` altrimenti.
- `claims.py::close` rifiuta di chiudere un nodo altrui solo se `alive(owner_pid)` (e non `--force`).
- `identity.py::alive(pid)` usa `os.kill(pid, 0)` + `ps` (POSIX) o `tasklist` (Windows): vale solo per processi di *questa* macchina.
- `config.py` sezione agent: `process_name`, `default_assignee`, `idle_hours`, `max_claims_per_session`.
- `doctor.py` e `report.py` consumano `claim_state`: l'avviso `lucchetto_fermo` scatta quando non è `live`.

Il punto debole: un claim scritto da un'altra macchina porta un PID che qui non significa niente. `alive(pid)` su un PID remoto può anche rispondere vero per pura coincidenza di riuso del numero.

## La decisione

### 1. Liveness remota = lease, non verifica di rete

Scartata la verifica via rete (chiedere al holder "sei vivo?"): richiede un indirizzo e un server sul holder, fallisce sotto partizione (irraggiungibile ma vivo), e duplica il trasporto che le ref git già danno (L01).

Scelto il lease: il claim porta `lease_until` (timestamp ISO assoluto), e ogni lettore lo confronta col proprio orologio. La liveness passa da fatto verificabile a ipotesi di freschezza. È la rinuncia standard dei distributed lock: non esiste un modo per distinguere un processo morto da uno vivo ma in silenzio, il TTL è il compromesso.

### 2. Il valore: TTL di default 3600 s (1 h)

Tre vincoli, due dei quali con numeri veri:

| vincolo | valore | come lo soddisfa 3600 s |
|---|---|---|
| ordine di grandezza sopra la latenza (0.49 s, L01) | ≥ ~5 s | 3600 / 0.49 ≈ 7300×, ~4 ordini di grandezza. Il pavimento di rete non è il vincolo stringente |
| non scadere mentre si lavora | ≥ cadenza di rinnovo | con rinnovo a ogni comando atlas del holder, la soglia è "un comando atlas almeno ogni TTL"; una sessione di lavoro tipica chiude ben prima |
| non bloccare per ore dopo una morte | più corto possibile | dopo una morte il nodo resta bloccato al massimo ~1 h, non "per ore"; e il furto di uno scaduto è comunque un atto deliberato (serve riscrivere la risposta e chiudere) |

Alternativa pesata e scartata: TTL = `idle_hours` (4 h), che renderebbe il blocco post-morte di ore, esattamente ciò che la domanda chiede di evitare. Altre due scartate: TTL di secondi con daemon di rinnovo (l'harness è command-based, non c'è un processo che vive durante il lavoro di un nodo) e auto-rilascio alla scadenza (un holder vivo ma partizionato perderebbe il nodo in silenzio, causando il pestarsi che la destinazione vuole evitare).

### 3. Il rinnovo

- A ogni `claim` di un nodo proprio (come l'heartbeat attuale).
- Per estensione, a ogni comando che carica il grafo mentre il holder è presente: il fatto stesso che il holder tocchi il progetto è il segnale di vita. Questo è il "rinnovo-su-lettura", ed è ciò che rende 3600 s sicuro per chi lavora: la soglia pratica è un comando atlas all'ora.
- Regola di sicurezza: il rinnovo tocca solo i claim con `e_mio` vero (host + identity), mai quelli altrui.

L'hook esatto del rinnovo-su-lettura è compito di L05; il modello richiede solo il contratto: chi rinnova almeno una volta per TTL tiene la lock.

### 4. Il PID locale resta

`lease_until` è scritto su ogni claim, così ogni lettore ha un segnale. Ma per un claim con `host` uguale al mio, la liveness autorevole resta `alive(pid)` (con l'idle su `idle_hours`). Il lease è la lente dei lettori remoti, il PID è la lente del holder. Il comportamento locale non cambia, e il caso single-machine non peggiora.

### 5. Come si presenta uno scaduto remoto

- `claim_state`: remoto `live` se `now < lease_until`, `dead` se scaduto. Nessun `idle` remoto: l'idle locale significa "processo vivo ma quieto", che da remoto non è osservabile.
- `close`: su un claim remoto rifiuta finché il lease è fresco, permette a lease scaduto (come per un morto locale). `--force` bypassa sempre. Il controllo `alive(owner_pid)` vale solo per i claim locali o legacy.
- `doctor`: l'avviso `lucchetto_fermo` scatta già quando claim_state non è `live`; va arricchito per dire host del holder e da quanto è scaduto il lease, così chi legge distingue una scadenza remota da una morte di processo locale.

### 6. Clock skew

Il lettore usa il proprio orologio; uno skew sposta il confine di ±skew. Difese:
1. Il TTL (1 h) è di gran lunga maggiore dello skew plausibile (secondi, pochi minuti con NTP): lo skew è assorbito dal margine.
2. Indurimento opzionale per L05: `doctor` segnala quando `lease_until` cade fuori da `now + [0, 2×TTL]`, sintomo di skew, invitando a sistemare NTP.

Direzione di rischio: holder avanti (lease pare più corto al lettore) rischia una scadenza precoce, mitigata dal margine e dal fatto che il furto è deliberato; holder indietro è sicuro, la lock dura di più.

## Campi e regole, in forma da implementare

Nuovi campi del claim:

```json
"claim": {
  "pid": 12345,
  "session": "...",
  "identity": "L02",
  "host": "macchina-a",
  "at": "2026-08-25T10:00:00+02:00",
  "heartbeat": "2026-08-25T10:30:00+02:00",
  "lease_until": "2026-08-25T11:30:00+02:00",
  "fingerprint": "..."
}
```

Regole:
- `host` = macchina del holder, default `socket.gethostname()`, sovrascrivibile via `ATLAS_HOST`.
- `lease_until` = `now + lease_ttl_seconds`, ISO con secondi, scritto al claim e a ogni rinnovo.
- `lease_ttl_seconds = 3600` nella sezione `agent` di `config.py`, configurabile.
- `e_mio` confronta host + identity: senza host, due macchine con la stessa `ATLAS_IDENTITY` si scambierebbero per la stessa persona e si rinfrescherebbero i lucchetti a vicenda.
- `close` remoto: rifiuta se `now < lease_until`, permette se scaduto; il PID check vale solo per host locale o legacy.
- Backward compat: claim senza `host` → locale (PID check); claim remoto senza `lease_until` → conservativamente fresco, mai morto.

## Confine con gli altri nodi

- **L03 (mutex su ref git)**: il mutex di acquisizione e la liveness sono due meccanismi distinti. La ref deve portare la scadenza (in modo che un `ls-remote` a ~0.49 s basti a giudicare la freschezza di tutte le lock in una volta); "rubare uno scaduto" usa lo stesso TTL.
- **L04 (dove abita il codice di rete)**: il modello del lease è trasport-agnostico, è solo dato nel claim propagato dalla sync esistente. Il confine no-rete di `payload/` non è toccato da questa decisione: il trasporto del lease è materia di L04.
- **L05 (il lease entra in claims.py)**: implementa campi, TTL, rinnovo-su-lettura, claim_state remoto, close remoto. Deve evitare "due verità sullo stesso nodo" tenendo distinte l'acquisizione (ref) e la liveness (lease nel claim).

## Nebbia residua

- Il valore 3600 s è un default motivato ma non misurato sul campo: se in esercizio gli agenti lavorano sessioni più lunghe senza toccare atlas, va alzato (o va introdotto un rinnovo esplicito, es. `atlas renew`).
- Lo skew effettivo fra le macchine di chi usa Atlas non è misurato: l'assorbimento da parte del TTL regge per skew di secondi/minuti; se uno skew anomalo comparisse, la soglia diagnostica di `doctor` lo mostrerebbe.
- Il comportamento di GitHub con molte ref `refs/atlas/*` è provato solo fino a poche decine; il limite raccomandato dai docs è 5.000 branch (nota L01).
