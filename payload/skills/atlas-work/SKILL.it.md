---
name: atlas-work
description: Lavora un nodo del grafo Atlas di questo progetto, dalla scelta sulla frontiera alla chiusura. Usala quando l'utente chiede di andare avanti col lavoro, di prendere il prossimo task, o nomina un nodo del grafo.
---

# Lavorare un nodo

Il grafo dice cosa è prendibile adesso. Un nodo per sessione, dal claim alla chiusura.

## 1. Orientati

```sh
python3 .atlas/bin/atlas status
```

Leggi anche la mappa del grafo attivo, `.atlas/graphs/<slug>/map.md`: la Destinazione dice dove si va, le Note dicono le preferenze permanenti, le Decisioni prese dicono cosa è già stato deciso e da quale nodo. Non serve aprire i ticket chiusi: la mappa è l'indice, si zooma solo su quello che serve davvero.

Se `status` segnala lucchetti orfani, sistemali prima di prendere altro.

## 2. Scegli e rivendica

Il nodo lo nomina l'utente. Se non lo nomina, prendi il primo della frontiera.

```sh
python3 .atlas/bin/atlas claim <ID>
```

**Rivendica prima di lavorare, non dopo.** Il claim serve a far sì che una sessione parallela salti questo nodo, e un claim messo alla fine non ha protetto niente.

Se il claim viene rifiutato perché la sessione ne tiene già uno, chiudi o rilascia quello prima. Non usare `--force` per abitudine.

## 3. Guarda il modo del nodo, e fermati se dice HITL

```sh
python3 .atlas/bin/atlas show <ID>
```

- **AFK**: lavori da solo. La risposta la scrivi tu.
- **HITL**: la risposta si costruisce parlando con l'utente. Porta la domanda, una alla volta, e aspetta. Rispondere al posto suo è il modo più veloce di rendere inutile il grafo.

Per i nodi `grilling` usa le skill `grilling` e `domain-modeling`, per i `prototype` la skill `prototype`, per i `research` la skill `research`, se sono installate. Le Note della mappa possono nominarne altre.

## 4. Lavora, e lascia traccia nel ticket

Il ticket è `.atlas/graphs/<slug>/tickets/<ID>.md`. Durante il lavoro annota in **Lavorazione** le alternative scartate e i link agli artefatti prodotti. Alla fine compila **Risposta**: è la sola cosa che `close` verifica, e serve a chi arriva dopo.

Se emerge qualcosa che meriterebbe un nodo suo, **non crearlo**. Appuntalo:

```sh
python3 .atlas/bin/atlas fog "quel che è emerso, in una riga"
```

e proponilo all'utente a fine nodo. La forma del grafo si cambia solo con uno script di mutazione, mai di slancio in mezzo a un altro lavoro.

## 5. Chiudi

```sh
python3 .atlas/bin/atlas close <ID> -s "la sintesi in una riga"
```

La sintesi finisce da sola in `map.md` sotto Decisioni prese, e la dashboard si rigenera. Se `close` rifiuta perché la Risposta è vuota, scrivila: non è un ostacolo da aggirare con `--force`.

**Un nodo per sessione, anche quando ne resta uno prendibile.** Chiuso il nodo, fermati e riferisci cosa si è deciso e cosa si è aperto. Il nodo successivo è una scelta dell'utente, non l'inerzia della sessione.
