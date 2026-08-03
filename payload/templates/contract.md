## Atlas: il grafo comanda il lavoro

Il lavoro di questo progetto è un grafo di task in `.atlas/`. Un nodo è un pezzo di lavoro dimensionato su una sessione, gli archi `blockedBy` sono le dipendenze, e la **frontiera** è l'insieme dei nodi aperti i cui blocker sono tutti chiusi. Non si sceglie cosa fare leggendo una lista: si guarda la frontiera.

```sh
.atlas/bin/atlas status              # frontiera, lucchetti, avanzamento
.atlas/bin/atlas claim <ID>          # rivendica, prima di toccare qualsiasi cosa
.atlas/bin/atlas close <ID> -s "..."  # chiude, dopo aver scritto la Risposta nel ticket
.atlas/bin/atlas fog "una riga"      # appunta ciò che è emerso e non ha ancora un nodo
```

### Un nodo per sessione

Il claim è un lucchetto, non un promemoria: porta il PID della sessione, e `claim` rifiuta se questa sessione ne tiene già uno. Per lavorare su più nodi in parallelo si aprono più sessioni, una per nodo. Il rifiuto si scavalca con `--force`, che esiste per i casi imprevisti e non per la fretta.

Un lucchetto è orfano quando il processo che l'ha preso non esiste più. `status` lo segnala, e va rilasciato o riconfermato prima di rivendicare altro.

### HITL e AFK

Ogni nodo dichiara chi scrive la sua risposta.

| Gesto | Autonomia |
|---|---|
| claim, release, close | sì, è contabilità |
| lavorazione e risposta di un nodo **AFK** | sì, è il lavoro stesso del nodo |
| risposta di un nodo **HITL** | no, si scrive insieme all'umano: è il senso della sigla |
| creare nodi, cambiare `blockedBy`, mettere fuori scopo | mai in autonomia, e comunque solo con uno script |

Un agente che risponde da solo a un nodo HITL ha rotto la regola più importante di questo contratto.

### La forma del grafo si cambia solo con codice

`graph.json` non si edita a mano, e la CLI non ha comandi che creano nodi o archi. Ogni modifica strutturale è uno script Python in `.atlas/scripts/` che passa da `core/mutate.py`:

```sh
.atlas/bin/atlas new-script aggiunge-ramo-deploy
.atlas/bin/atlas exec .atlas/scripts/003-aggiunge-ramo-deploy.py
```

Lo script gira in una sola transazione e il grafo viene validato prima di essere scritto, quindi un ciclo o un arco verso un nodo inesistente lo fanno fallire senza toccare il file. Gli script restano versionati: sono la storia delle modifiche alla mappa.

Quel che scopri lavorando un nodo e che meriterebbe un nodo suo va **proposto**, non creato: intanto si appunta con `atlas fog`.

### Quando un nodo è fatto

| Tipo | Fatto quando |
|---|---|
| `grilling` | la decisione è scritta e l'artefatto che produce esiste |
| `research` | la risposta cita fonti lette adesso, con link e data, non ricordate |
| `prototype` | l'artefatto si può guardare, e il ticket dice cosa si è imparato e cosa si è scartato |
| `task` | il lavoro è fatto e verificato, con la prova descritta nel ticket |

`close` verifica una cosa sola, che la sezione **Risposta** del ticket sia compilata. Il resto lo dichiara chi chiude. Che la risposta sia anche vera non lo può verificare nessuna macchina, e l'unica difesa è che la scriva chi ha fatto il lavoro mentre ce l'ha fresco.

### Più grafi

Un grafo per epic, ciascuno isolato in `.atlas/graphs/<slug>/` con la sua mappa e la sua dashboard. Lo switch è a carico di chi lavora: `atlas use <slug>`, oppure `--graph <slug>` sul singolo comando.
