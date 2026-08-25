---
name: atlas-research
description: Lavora un nodo `research` andando alle fonti primarie e scrivendo un documento che cita ogni affermazione con link e data. Usala sui nodi `research` del grafo e quando serve sapere qualcosa che sta fuori da questa cartella di lavoro, prima di decidere basandosi sui ricordi.
---

# Rispondere a un nodo di ricerca

Il nodo `research` è AFK: la risposta la scrivi tu, senza passare dall'utente. Proprio per questo il contratto gli mette addosso il vincolo più duro di tutti i tipi, che **la risposta citi fonti lette adesso, con link e data, non ricordate**. Un modello ricorda le API di un anno fa con la stessa sicurezza con cui ricorda quelle di ieri, e un nodo di ricerca chiuso su un ricordo avvelena ogni decisione che ci si appoggia sopra.

## 1. Vai alla fonte che possiede il fatto

Fonti primarie: la documentazione ufficiale, il codice sorgente, la specifica, l'API di prima parte, il changelog del progetto. Non il riassunto che qualcuno ne ha fatto. Ogni affermazione si segue a ritroso fino a chi la possiede davvero, e se la catena si interrompe su un blog, quello è un indizio, non una fonte.

Se la lettura è lunga puoi delegarla a un agente in background e continuare intanto, ma il lucchetto e la Risposta restano di questa sessione: chi ha rivendicato il nodo è chi risponde.

## 2. Scrivi il documento

Scrivi un file markdown dove il progetto tiene già note di questo genere. Se una convenzione non c'è, mettilo in un posto sensato e dillo nella Risposta.

Ogni affermazione porta il suo link e la **data in cui l'hai letta**, in forma ISO. La data non è burocrazia: una pagina di documentazione cambia sotto i piedi, e fra sei mesi l'unico modo per sapere se quel che hai scritto vale ancora è sapere quando valeva.

Tre casi che vanno scritti invece che appianati:

- **Le fonti si contraddicono.** Riportale entrambe, di' quale hai preferito e perché. Scegliere in silenzio nasconde proprio l'informazione che serviva.
- **La risposta non c'è.** Dichiara la copertura parziale: cosa hai trovato, cosa no, dove hai cercato. Una lacuna dichiarata è un risultato; una lacuna riempita a intuito è un danno.
- **La versione conta.** Scrivi il numero di versione accanto al fatto, ogni volta che il fatto ne dipende.

## 3. Chiudi

La Risposta del ticket è la **sintesi con i link portanti**, non il documento incollato: il documento è l'artefatto, e vive in un posto solo. Chi legge il ticket deve capire cosa si è scoperto e quali decisioni ora sono possibili, senza aprire il file.

```sh
atlas close <ID> -s "l'API supporta il batch, ma non oltre 100 elementi" --artefatti docs/ricerca-api-batch.md
```

Se durante la lettura emerge qualcosa che meriterebbe un nodo suo, non crearlo: `atlas fog "..." --for <ID>` e proponilo a fine nodo.
