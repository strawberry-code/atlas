# L01 · Le ref custom reggono su GitHub?

> Nodo di ricerca del grafo `260825-sync-distribuita` (ramo "Lucchetto fra macchine").
> Domanda: GitHub accetta push su `refs/atlas/*`, e quanto costa in latenza un `ls-remote` reale?
> Data prova: 2026-08-25. Remote usato: `https://github.com/strawberry-code/atlas.git` (auth `gh`/`GITHUB_TOKEN`, scope `repo`).

## Risposta in una riga

Sì: GitHub accetta push, lettura e cancellazione su `refs/atlas/*` senza alcun avviso, e un `ls-remote` reale costa circa 0.5 s (mediana 0.49 s su 6 prove, repo con 62 ref).

## Metodo

Fonte primaria = comportamento reale di GitHub, provato sul campo contro il remote del progetto. Completata la lettura della documentazione ufficiale sui limiti di repo. Nessuna traccia lasciata sul remote: tutte le ref usate sono state create e cancellate nello stesso ciclo.

## Prove

### 1. Latency di `git ls-remote` (6 run, HTTPS, auth token)

Comando: `git ls-remote origin`, misurato con `date +%s.%N` attorno alla chiamata.

| run | rc | refs | wall (s) |
|-----|----|------|----------|
| 1 (freddo) | 0 | 62 | 0.724 |
| 2 | 0 | 62 | 0.491 |
| 3 | 0 | 62 | 0.500 |
| 4 | 0 | 62 | 0.485 |
| 5 | 0 | 62 | 0.483 |
| 6 | 0 | 62 | 0.462 |

Mediana dei 6: **0.487 s**. Passo tipico a caldo: **0.46-0.50 s**. Il primo run (handshake + eventuale cache credenziali) è ~0.72 s.

Nota: il tempo scala con il payload di advertisement (tutte le ref della repo, qui 62 righe). Aggiungere ref di lock/sync aumenta il payload di una riga per ref: trascurabile finché il numero di lock vivi è basso.

### 2. Push su `refs/atlas/*`: accettato

```text
$ git push origin 8c932ed1e49126748a04e78bf02e0a40ef144641:refs/atlas/test-l01-1787689274
To https://github.com/strawberry-code/atlas.git
 * [new reference]   8c932ed1e49126748a04e78bf02e0a40ef144641 -> refs/atlas/test-l01-1787689274
```

rc=0. Nessun avviso, nessun trigger CI (non è un ramo sotto `refs/heads`, quindi protezioni rami e CI sui branch non si applicano; non è un tag).

### 3. La ref è reale e leggibile

```text
$ git ls-remote origin | grep "atlas/"
8c932ed1e49126748a04e78bf02e0a40ef144641  refs/atlas/test-l01-1787689274
```

La ref vive nell'advertisement e si può leggere via `git fetch`/`git ls-remote`. Non appare però in UI (non è un branch né un tag): il canale è invisibile a chi naviga da browser, visibile solo via git.

### 4. Cancellazione: accettata, senza tracce

```text
$ git push origin :refs/atlas/test-l01-1787689274
To https://github.com/strawberry-code/atlas.git
 - [deleted]         refs/atlas/test-l01-1787689274
```

rc=0. Verifica finale: `git ls-remote origin | grep "atlas/"` non trova nulla (rc=1).

### 5. Compare-and-swap (proprietà che serve al lucchetto)

Acquisire = push di una ref nuova; contendere = push di un commit diverso sulla stessa ref senza `--force`.

```text
$ git push origin 8c932ed...:refs/atlas/test-cas-...   # A crea il lucchetto
 * [new reference]  ... -> refs/atlas/test-cas-...
$ git push origin 323a4fb...:refs/atlas/test-cas-...   # B contende con un commit diverso
 ! [rejected]  323a4fb... -> refs/atlas/test-cas-... (non-fast-forward)
error: failed to push some refs
```

rc=1 sul contendente: il primo che scrive vince. Nota: la semantica è quella di git (`non-fast-forward`), non un check dedicato "ref esiste". Due token di lock indipendenti non sono mai antenati l'uno dell'altro, quindi un secondo acquirente viene sempre rifiutato; l'unica via per spostare la ref è `--force` (o un fast-forward), che il protocollo del lucchetto deve vietare.

## Documentazione ufficiale (fonte secondaria, letta 2026-08-25)

- [Repository limits · GitHub Docs](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits): unico limite sui rami = raccomandazione di non superare **5.000 branch**. Molti branch aggiungono dati inutili alle fetch, possono rallentare i trasferimenti o portare a throttling. Non documenta limiti su `refs/*` né su tag.
- La pagina [Pushing commits to a remote repository](https://docs.github.com/en/get-started/using-git/pushing-commits-to-a-remote-repository) non documenta restrizioni sui namespace di ref custom.
- Nessuna pagina ufficiale documenta esplicitamente `refs/atlas/*`: l'accettazione è provata empiricamente (sopra), la documentazione non la vieta e non la cita.

## Avvertenze operative

- **Autenticazione**: il push richiede un token con scope `repo` e permesso di scrittura sulla repo. `ls-remote` su repo pubblica non richiede auth.
- **Ref invisibili in UI**: `refs/atlas/*` non compaiono tra branch/tag. Operazioni solo via git. Un umano che guarda la repo da browser non vede i lucchetti.
- **Crescita del conteggio ref**: ogni lock vivo = una riga nell'advertisement. Con heartbeat persistenti per macchina, il conteggio cresce con il numero di macchine; sotto le migliaia è irrilevante, sopra i 5.000 si entra nella zona raccomandata come no-go dai docs GitHub.
- **Rilascio/race**: la delete è incondizionata; due macchine che rilasciano lo stesso lock → la seconda delete di una ref inesistente è un errore (da gestire come idempotente).
- **Niente CI, niente protezioni**: il canale è "pulito" (non triggera workflow né branch protection), ma anche senza i guard-rail che quelle danno.

## Nebbia residua

- GitHub non documenta formalmente il supporto di `refs/*` custom: la prova è su un solo remote (strawberry-code/atlas, repo normale). Repo con policy aziendali, GHES o hook di pre-receive potrebbero comportarsi diversamente. Verifica sul remote di destinazione prima di affidarci il protocollo.
- La latenza misura qui (connessione, geografia, token) non è una costante: è un ordine di grandezza per una repo piccola da questa macchina.
