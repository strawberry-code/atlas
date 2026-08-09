---
name: atlas-work
description: Lavora un nodo del grafo Atlas di questo progetto, dalla scelta sulla frontiera alla chiusura. Usala quando l'utente chiede di andare avanti col lavoro, di prendere il prossimo task, o nomina un nodo del grafo.
---

# Lavorare un nodo

Il grafo dice cosa è prendibile adesso. Un nodo per sessione, dal claim alla chiusura. Se il contratto di questo progetto non ti è già in contesto, `atlas how-to` te lo stampa insieme ai comandi, alle mutazioni e ai path.

## 1. Orientati

```sh
python3 .atlas/bin/atlas status
```

Leggi anche la mappa del grafo attivo, `.atlas/graphs/<slug>/map.md`: la Destinazione dice dove si va, le Note dicono le preferenze permanenti, le Decisioni prese dicono cosa è già stato deciso e da quale nodo, chiusura o rilascio motivato. Non serve aprire i ticket chiusi: la mappa è l'indice, si zooma solo su quello che serve davvero.

Se `status` segnala lucchetti orfani o fermi, sistemali prima di prendere altro. Con più nodi prendibili insieme, `atlas next` li ordina per impatto (quanti ne sblocca, quanto cammino resta), come suggerimento.

## 2. Scegli, rivendica e leggi il contesto

Il nodo lo nomina l'utente. Se non lo nomina, guarda `atlas next` o prendi il primo della frontiera.

```sh
python3 .atlas/bin/atlas take <ID>
```

`take` rivendica il nodo e stampa nello stesso passo la sua scheda (ramo, tipo, modo, stato), la domanda, le Risposte dei suoi bloccanti e la nebbia che lo nomina — lo stesso pacchetto che dà `atlas brief <ID>`, senza doverlo ricostruire a mano rileggendo ticket su ticket.

**Rivendica prima di leggere, non dopo.** È il motivo per cui `take` esiste al posto di `show` seguito da `claim`: il claim serve a far sì che una sessione parallela salti questo nodo, e uno preso alla fine non ha protetto niente.

Se il claim viene rifiutato perché questa identità ne tiene già uno, chiudi o rilascia quello prima. Non usare `--force` per abitudine.

## 3. Fermati se il nodo dice HITL

La riga sotto il titolo, stampata da `take`, dice ramo, tipo, modo e stato.

- **AFK**: lavori da solo. La risposta la scrivi tu.
- **HITL**: la risposta si costruisce parlando con l'utente. Porta la domanda, una alla volta, e aspetta. Rispondere al posto suo è il modo più veloce di rendere inutile il grafo.

Per i nodi `grilling` usa le skill `grilling` e `domain-modeling`, per i `prototype` la skill `prototype`, per i `research` la skill `research`, se sono installate. Le Note della mappa possono nominarne altre.

## 4. Lavora, e lascia traccia nel ticket

Il ticket è `.atlas/graphs/<slug>/tickets/<ID>.md`. Scrivi da **Lavorazione** in giù: quel che sta sopra il commento `<!-- /atlas:auto -->` discende dal grafo e si riscrive da sé, quindi correggerlo a mano è tempo perso. Durante il lavoro annota in **Lavorazione** le alternative scartate e i link agli artefatti prodotti. Alla fine compila **Risposta**: è la sola cosa che `close` verifica, e serve a chi arriva dopo.

Se emerge qualcosa che meriterebbe un nodo suo, **non crearlo**. Appuntalo, indirizzato a un nodo se lo riguarda:

```sh
python3 .atlas/bin/atlas fog "quel che è emerso, in una riga" --for <ID>
```

e proponilo all'utente a fine nodo. La forma del grafo si cambia solo con uno script di mutazione, mai di slancio in mezzo a un altro lavoro. Per farne un nodo c'è un esempio pronto in `.atlas/scripts/000-promote-fog.py`: si compila con l'indice della voce e i campi del nodo, e si lancia con `atlas exec`.

## 5. Chiudi

```sh
python3 .atlas/bin/atlas close <ID> -s "la sintesi in una riga"
```

Se vuoi lasciare un ordine di grandezza di quanto è costato (chiamate, token, tempo), aggiungi `-c/--costo "..."`. I file prodotti non devi elencarli: in una repo git `close` li ricava da solo, guardando cosa hai toccato da quando hai rivendicato il nodo. Se lavori in parallelo con altri nodi, questa deduzione salta e devi dichiarare gli artefatti con `--artefatti path/uno path/due`. Con `--artefatti` senza argomenti il campo rimane vuoto. Nel ticket, le sotto-sezioni **Scelte non canoniche**, **Debito dichiarato** e **Autorizzazioni ricevute** sotto Risposta sono facoltative: usale quando c'è davvero qualcosa da dire, altrimenti lasciale vuote.

La sintesi finisce da sola in `map.md` sotto Decisioni prese, e la dashboard si rigenera. Se `close` rifiuta perché la Risposta è vuota, scrivila: non è un ostacolo da aggirare con `--force`.

**Un nodo per sessione, anche quando ne resta uno prendibile.** Chiuso il nodo, fermati e riferisci cosa si è deciso e cosa si è aperto. Il nodo successivo è una scelta dell'utente, non l'inerzia della sessione.
