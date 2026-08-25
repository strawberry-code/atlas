# Sincronizzazione fra macchine

> Grafo `260825-sync-distribuita` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Due agenti su due macchine lavorano lo stesso grafo senza pestarsi: le chiusure si fondono da sole, un nodo preso su una macchina risulta preso sull'altra, e la dashboard mostra chi tiene cosa mentre lo tiene.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
- Trial sul campo fino al 2026-09-09: due macchine, due identità, lavoro vero. Dopo OGNI merge lancia `atlas doctor` e annota i `concurrent close` / `divergent state` che riporta. La regola di decisione e l'alternativa stanno in C03 e in docs/adr/0001-centralized-graph-service.md.

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
- **L01** Le ref custom reggono su GitHub?: Sì: GitHub accetta push, lettura e delete su refs/atlas/* con CAS per il lucchetto; ls-remote ~0.49 s · [ticket](tickets/L01.md)
- **A01** Come divergono davvero due copie del grafo: Chiusure su nodi diversi si fondono da sole; conflitti veri solo su chiusura/presa dello stesso nodo, falsi su meta.updated, array a riga unica e ordine dei nodi · [ticket](tickets/A01.md)
- **L02** Da liveness a lease: Il claim remoto passa da liveness-PID a lease: scadenza lease_until di default 1 h, rinnovo a ogni comando del holder, il PID resta la liveness locale · [ticket](tickets/L02.md)
- **V01** atlas serve: la dashboard smette di essere un file da riaprire: atlas serve: dashboard viva su HTTP solo stdlib, rigenera sull'mtime del grafo e spinge al browser con SSE, senza toccare il rendering · [ticket](tickets/V01.md)
- **L03** Mutex su git refs, fuori dal motore: Le quattro primitive reggono su refs git, con force-with-lease per il CAS nel varco di corsa; il possesso resta al protocollo · [ticket](tickets/L03.md)
- **L04** Dove abita il codice di rete: Confine nuovo: semantica e interfaccia del lucchetto remoto nel motore, trasporto git-refs in atlascli, la regola no-rete di payload/ regge senza seconda eccezione · [ticket](tickets/L04.md)
- **A02** Fusione a tre vie per nodo: Fusione a tre vie per id di nodo in merge.py: driver git 'atlas merge-graph %O %A %B', conflitti dichiarati in conflicts e uscita 1, chiusura e claim atomici, array fusi per elemento, ordine canonico · [ticket](tickets/A02.md)
- **A03** Il driver arriva nei progetti ospiti: L'install registra da se' il merge driver git (config + .gitattributes) nei progetti che sono repo, idempotente e muto fuori dalle repo · [ticket](tickets/A03.md)
- **L05** Il lease entra in claims.py: Lease e lucchetto remoto convivono: la verità remota sta nella ref, quella locale nel claim, e il claim si scrive solo a ref libera o scaduta · [ticket](tickets/L05.md)
- **A04** Quel che non si fonde resta un conflitto dichiarato: Il merge dichiara e non risolve chiusura/presa/stato/campo descrittivo; doctor e 'atlas conflicts' li mostrano, '--resolve' li dichiara risolti togliendo il campo · [ticket](tickets/A04.md)
- **V02** I lucchetti delle altre macchine nella vista: Passo da 30 s per i lucchetti remoti nella vista di atlas serve, pannello dedicato e degradazione senza rete. · [ticket](tickets/V02.md)
- **L06** Il battito si rinnova da solo: Il battito si rinnova da solo: il dispatcher rinnova i claim _mio a ogni comando che carica il grafo, quando manca meno di metà del TTL · [ticket](tickets/L06.md)
- **L07** I bordi: finestra condivisa e assenza di rete: La finestra condivisa vede le ref remote (elenca); senza rete le letture degradano con avviso e le mutazioni restano fail-closed · [ticket](tickets/L07.md)
- **C01** Documenti in pari: README, contratto e how-to in pari: serve, merge-graph, conflicts, merge driver e il claim da un'altra macchina con la politica senza rete di L07 · [ticket](tickets/C01.md)
- **C02** Prova su due cloni veri: Prova su due cloni veri: il merge driver fonde per nodo in una git-merge reale, i conflitti veri si dichiarano e si risolvono con atlas conflicts, la ref remota esclude e consegna fra due macchine, senza rete si degrada e si chiude · [ticket](tickets/C02.md)

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
- sotto --dry-run due messaggi dell'install sono al passato ('contratto appeso', 'aggiunte N righe') accanto a 'scriverebbe'
- manca una mutazione per rinominare o togliere un ramo: il ramo di default creato da create_graph si può solo riscrivere a mano
- per L05: un rinnovo del lease con la stessa identità (solo lease_until/host diversi) cade oggi nella famiglia 'status' ed è un falso conflitto: A01 lo rimanda alla politica del lease del ramo L, e il claim non porta ancora lease_until nei grafi reali

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
