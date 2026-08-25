---
name: atlas-domain-modeling
description: Costruisce e affila il linguaggio del dominio mentre si decide: sfida i termini ambigui, li fissa in un glossario, e registra come ADR le sole decisioni che è caro rovesciare. Usala insieme alle due skill di grilling sui nodi che decidono qualcosa, e ogni volta che una parola del progetto viene usata con due significati diversi.
---

# Affilare il linguaggio del dominio

È una disciplina attiva, non una lettura: si sfidano i termini, si inventano scenari limite, si scrive il glossario nel momento in cui una parola si è chiarita. Leggere il glossario per sapere come si chiamano le cose lo fa qualsiasi skill in una riga; questa serve quando il modello lo stai **cambiando**.

Si usa in coppia con `atlas-strategic-grilling` e `atlas-tactical-grilling`: la griglia porta le domande, questa fissa le parole con cui la risposta viene scritta. Senza, il grafo accumula ticket che dicono "account" intendendo tre cose diverse.

Il glossario del dominio non ha niente a che vedere con `vocab` in `.atlas/config.json`, che è il vocabolario dell'harness (tipi, modi, stati) e non del progetto.

## Durante la sessione

**Sfida contro il glossario.** Quando l'utente usa un termine in conflitto con quello già fissato, dillo subito: «il glossario dice che *cancellazione* è X, ma tu sembri intendere Y: quale delle due?».

**Affila il linguaggio vago.** Davanti a un termine sovraccarico, proponi quello preciso: «dici *account*: intendi il Cliente o l'Utente? Sono due cose diverse».

**Porta scenari concreti.** Quando si discutono relazioni fra concetti, inventa il caso limite che costringe a essere precisi sul confine. È lì che i modelli sbagliati si rompono, non nelle definizioni generali.

**Incrocia col codice.** Quando l'utente afferma come funziona qualcosa, vai a vedere se il codice è d'accordo. Se si contraddicono, la contraddizione va portata a galla subito, non aggirata.

## Dove si scrive

**Il glossario** sta in un `CONTEXT.md` alla radice del progetto, creato quando il primo termine si risolve e aggiornato sul momento, mai in blocco a fine sessione. Una voce è il termine, una o due frasi che dicono **cosa è**, non cosa fa, e i sinonimi da evitare:

```md
**Ordine**:
La richiesta di un cliente, dal carrello alla consegna.
_Evita_: acquisto, transazione
```

Solo i termini specifici di questo dominio. Concetti generali di programmazione non ci entrano, per quanto il progetto li usi. Il `CONTEXT.md` è un glossario e nient'altro: non è una specifica, non è un blocco per appunti, e non ospita decisioni implementative.

**Un ADR** si propone solo quando valgono tutte e tre le condizioni: la decisione è **cara da rovesciare**, è **sorprendente senza il contesto** (fra un anno qualcuno si chiederà perché), ed è il frutto di un **compromesso vero**, con alternative reali che sono state scartate. Se ne manca una, l'ADR non serve. Basta un paragrafo in `docs/adr/NNNN-slug.md`, numerato in coda agli esistenti. Deve risultare che la decisione è stata presa e se ne deve capire il perché, mentre le sezioni del documento non interessano nessuno.

## Come atterra nel nodo

Le parole fissate e gli ADR scritti sono artefatti del nodo, e vanno dichiarati alla chiusura:

```sh
atlas close <ID> -s "Ordine e Spedizione sono due entità distinte" --artefatti CONTEXT.md docs/adr/0003-ordine-e-spedizione.md
```

Se una preferenza sul linguaggio deve valere per tutto il grafo e non solo per questo nodo, il posto è le Note della mappa, con `mutate.note_add` dentro uno script di mutazione.
