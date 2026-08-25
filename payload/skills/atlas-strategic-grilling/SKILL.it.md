---
name: atlas-strategic-grilling
description: Interroga l'utente senza sconti su un piano o un disegno, una domanda alla volta, finché non vi siete capiti davvero. Usala sui nodi `grilling` che decidono qualcosa di strutturale o irreversibile (architettura, contratto, forma di un'interfaccia, scelta di prodotto) e ogni volta che l'utente chiede di essere grigliato su un piano prima di costruirlo.
---

# Grigliare una decisione di fondo

Questa è la griglia lunga, quella che si usa quando la decisione ne vincola molte altre e sbagliarla costa una riscrittura. Non ha un budget di domande né una struttura in fasi: si va avanti finché l'albero del disegno non è percorso fino in fondo. Se il nodo è invece circoscritto, di codice, con una manciata di scelte da chiudere in una sessione, la skill giusta è `atlas-tactical-grilling`.

## Il metodo

Il cuore è la skill `grilling` di Matt Pocock, che Atlas distribuisce perché il tipo di nodo `grilling` non abbia senso solo sulle macchine dove quella skill è installata.

> Intervistami senza tregua su ogni aspetto di questo piano, finché non ci siamo capiti davvero. Percorri ogni ramo dell'albero del disegno, sciogliendo una alla volta le dipendenze fra le decisioni. Per ogni domanda, proponi la risposta che consiglieresti.
>
> Fai le domande una alla volta, e aspetta la mia risposta prima di continuare. Farne più di una insieme disorienta.
>
> Se un fatto si può trovare esplorando il codice, cercalo invece di chiedermelo. Le decisioni, però, sono mie: mettimele davanti una per una e aspetta che risponda.
>
> Non mettere in atto il piano finché non confermo che ci siamo capiti.

Le quattro righe si tengono per la coda. Una domanda alla volta serve a poco se poi la risposta non cambia la domanda dopo, e proporre sempre la risposta che consiglieresti è quel che distingue un interrogatorio da un questionario: l'utente corregge una proposta molto più in fretta di quanto riempia un foglio bianco.

## Dove atterra, in un nodo Atlas

Il nodo `grilling` è quasi sempre HITL, e la griglia è il suo lavoro, non un preliminare. Mentre vai, annota in **Lavorazione** del ticket le alternative che l'utente ha scartato e il perché: è quella la parte che nessuno ricostruisce dopo. Alla fine, in **Risposta**, scrivi la decisione presa, non il verbale dell'intervista.

Se la decisione produce un artefatto (un ADR, un documento di disegno, uno schema), quell'artefatto deve esistere prima della chiusura: il contratto dice che un nodo `grilling` è fatto quando la decisione è scritta **e** l'artefatto che produce esiste. Per il vocabolario di dominio e gli ADR usa anche `atlas-domain-modeling`.

Quel che emerge e meriterebbe un nodo suo non si trasforma in nodo di slancio: si appunta con `atlas fog "..." --for <ID>` e si propone all'utente a fine nodo.
