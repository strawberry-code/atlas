---
name: atlas-sync
description: Riporta la copia del grafo Atlas di questo progetto in pari con quella degli altri agenti e pubblica il proprio lavoro, anche quando `graph.json` è andato in conflitto. Usala prima di un push su un grafo condiviso, o quando un merge tocca il grafo.
---

# Allineare un grafo condiviso

Il grafo condiviso si cambia solo con script di mutazione. Quando due agenti lavorano lo stesso grafo su copie diverse, `graph.json` finisce in un merge di git.

**Quel merge lo fa il driver, non tu.** Atlas registra all'installazione un merge driver (una riga in `.gitattributes` e una sezione nel config git locale) che fonde `graph.json` per id di nodo invece che per riga: due chiusure su nodi diversi si compongono da sole, il file resta JSON valido e non ci finiscono mai marker di git. Questa skill copre quel che il driver non può decidere da solo.

## 1. Prima di pubblicare, chiudi la sessione

```sh
atlas status
```

`status` mostra i lucchetti: se ce n'è uno tuo ancora aperto, chiudi il nodo con `atlas close <ID> -s "..."` oppure molla con `atlas release <ID>`. Il lavoro va committato prima di passare oltre.

## 2. Fondi, e lascia lavorare il driver

```sh
git fetch
git merge origin/<ramo>
```

Se il merge passa pulito, il grafo è già fuso bene e restano solo i passi 4 e 5. Non aprire `graph.json`, non fare `git checkout origin/<ramo> -- graph.json`: butteresti via proprio la fusione appena fatta.

## 3. Se git dichiara conflitto sul grafo

Il driver esce in conflitto quando i due rami hanno cambiato lo stesso nodo in modi inconciliabili, per esempio due chiusure diverse dello stesso nodo o due claim concorrenti. Il file che ti lascia è comunque JSON valido, con l'elenco di quel che non ha saputo decidere.

```sh
atlas conflicts
```

Stampa su quali nodi e su quali campi si è fermato, e di che tipo sono: `concurrent close`, `concurrent claim`, `divergent state`, `value conflict`.

Poi decidi tu, nodo per nodo, e correggi. Una chiusura che è avvenuta davvero sull'altra copia e che nella fusione si è persa si riporta con `mutate.restore_closure` dentro uno script, coi metadati originali letti dal diff, mai inventati. Quando il grafo dice il vero:

```sh
atlas conflicts --resolve
```

Toglie l'annotazione dichiarando che l'hai risolto tu. Non decide niente al posto tuo: è una firma, non un rimedio.

## 4. Rinumera i tuoi script in coda ai loro

Gli script sono file distinti e non confliggono quasi mai, ma due copie possono aver creato lo stesso numero.

```sh
atlas renumber <i tuoi file>
```

Li sposta dopo il massimo degli altri, nell'ordine che indichi, con `git mv` dove serve. Senza argomenti compatta la numerazione; `--dry-run` mostra le rinomine senza farle.

## 5. Verifica e pubblica

```sh
atlas doctor
atlas status
```

Prima del commit, `doctor` e `status` devono passare puliti. `doctor` riporta anche i conflitti ancora annotati, quindi è lui a dirti se il passo 3 è finito davvero. Il push è un gesto che l'utente ha chiesto, non l'ultimo passo automatico della procedura. Chiedilo, se non è già stato detto.

## Cosa non fare

- **Non fondere `graph.json` in un editor** e non prendere una delle due versioni con `git checkout origin/<ramo> --`. Il driver ha già fatto il lavoro per id di nodo, e sovrascriverlo lo annulla.
- **Non usare `--ours` o `--theirs`.** Fra merge e rebase le due parole si invertono, ed è l'errore che si fa. Se proprio devi nominare un ramo, scrivilo per esteso.
- **Non rieseguire uno script già applicato** sul grafo che hai preso come base: i suoi nodi ci sono già, e l'esecuzione muore dicendo che l'id esiste.
- **Non usare `restore_closure` per chiudere un nodo vero.** Un nodo si chiude con `atlas close`, che verifica il lucchetto e la Risposta scritta nel ticket.
- **Non lanciare `atlas conflicts --resolve` per far sparire l'avviso** senza aver guardato i nodi che nomina. Dichiara che il grafo dice il vero, e se non lo dice il difetto resta, solo silenzioso.
