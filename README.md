# Atlas

Harness di task a grafo per progetti guidati da agenti. Ogni task è un nodo, le dipendenze sono archi, e in ogni momento esiste una **frontiera**: i nodi aperti i cui blocker sono tutti chiusi, cioè il lavoro prendibile adesso.

Nasce come generalizzazione del `wayfinder/` di Ars Goetia, reso indipendente dal progetto ospite e capace di reggere più grafi in parallelo.

## Installazione

Copia `dist/atlas-install.py` dentro il progetto e lancialo:

```bash
python3 atlas-install.py --yes --graph epic-primo
```

L'installer scompatta l'harness in `.atlas/`, registra l'hook di fine sessione in `.claude/settings.json` senza toccare gli hook già presenti, crea i symlink delle due skill sotto `.claude/skills/` e appende il contratto operativo a `CLAUDE.md` in un blocco delimitato. È idempotente: rilanciarlo aggiorna il motore e lascia intatti configurazione, grafi e script.

Serve Python 3.10 o superiore su un sistema POSIX. Nessuna dipendenza esterna, nessun venv, nessuna rete.

## Le due idee

**Il grafo comanda il lavoro.** Non si sceglie cosa fare leggendo una lista: si guarda la frontiera. Un nodo si rivendica prima di toccarlo, e il claim è un lucchetto legato al PID della sessione, non un post-it. Quando il processo che l'ha preso non esiste più, il lucchetto è orfano e va riconfermato o rilasciato.

**HITL o AFK.** Ogni nodo dichiara se la risposta si scrive insieme all'umano oppure se l'agente la scrive da solo. È la riga che separa il lavoro delegabile dalla decisione che nessuno può prendere al posto tuo.

## Uso quotidiano

```bash
.atlas/bin/atlas status              # frontiera, nodi in lavorazione, avanzamento
.atlas/bin/atlas claim F01           # rivendica
.atlas/bin/atlas close F01 -s "..."  # chiude, dopo aver scritto la Risposta nel ticket
.atlas/bin/atlas fog "una riga"      # appunta ciò che è emerso e non ha ancora un nodo
.atlas/bin/atlas render --open       # rigenera la dashboard e la apre
.atlas/bin/atlas graphs              # elenca i grafi del progetto
.atlas/bin/atlas use epic-secondo    # cambia grafo attivo
```

## Come si modifica un grafo

Mai a mano. `graph.json` si tocca solo eseguendo uno script Python che passa dall'API di `core/mutate.py`:

```bash
.atlas/bin/atlas new-script aggiunge-ramo-deploy   # crea .atlas/scripts/003-aggiunge-ramo-deploy.py
.atlas/bin/atlas exec .atlas/scripts/003-aggiunge-ramo-deploy.py
```

Gli script restano in `.atlas/scripts/`, numerati e versionati: sono la storia delle modifiche al grafo, rileggibile in diff e rieseguibile. Ogni mutazione valida il grafo prima di scrivere, quindi un ciclo o un arco verso un nodo inesistente vengono rifiutati e la transazione non tocca il disco.

## Più grafi nello stesso progetto

Un grafo per epic. Ognuno vive in `.atlas/graphs/<slug>/` con il suo `graph.json`, i suoi ticket e la sua dashboard, isolato dagli altri. Lo switch è a carico di chi lavora, con `atlas use <slug>`, con `--graph <slug>` sul singolo comando, o con la variabile `ATLAS_GRAPH` quando due sessioni lavorano grafi diversi in parallelo.

## Sviluppo di Atlas stesso

```bash
python3 -m unittest discover -s tests -v   # test del motore
python3 build.py                            # rigenera dist/atlas-install.py
```

`payload/` è ciò che finisce dentro il progetto ospite. `build.py` lo impacchetta in un tar.gz codificato base64 dentro un unico file installabile.
