"""Lettura normalizzata degli assegnatari (il campo owner di ogni nodo).

Spezzato da model.py quando il campo owner e' diventato un vettore di persone:
con la forma nuova model.py sfondava le 200 righe. Da qui si legge sempre la
forma normalizzata, mai quella grezza scritta a mano nel JSON.
"""


def chiave_nome(nome: str) -> tuple[str, str]:
    """L'ordine unico dei nomi di persona: alfabetico senza guardare le maiuscole,
    col nome esatto come spareggio per non dipendere dall'ordine di arrivo."""
    return (nome.casefold(), nome)


def owners_of(node: dict) -> list[str]:
    """I nomi di persona del nodo, distinti e in ordine, in qualunque forma li trovi.

    Il grafo e' un file versionato che si modifica anche a mano, quindi il campo
    owner arriva qui come stringa vecchia ('cristiano+pedro'), come lista nuova o
    non arriva affatto. Il '+' si scioglie solo sulla forma stringa, che era la
    convenzione a mano per i task congiunti; in una lista un '+' dentro un nome e'
    un nome, non un separatore. Non solleva mai: e' la porta di lettura e deve
    reggere un file scritto male.
    """
    valore = node.get("owner")
    if valore is None:
        return []
    if isinstance(valore, str):
        pezzi = [p for pezzo in valore.split(",") for p in pezzo.split("+")]
    elif isinstance(valore, (list, tuple)):
        pezzi = [p for elemento in valore for p in str(elemento).split(",")]
    else:
        pezzi = [str(valore)]
    nomi = []
    for pezzo in pezzi:
        pulito = " ".join(pezzo.split())
        if pulito and pulito not in nomi:
            nomi.append(pulito)
    return sorted(nomi, key=chiave_nome)


def owners(data: dict) -> dict[str, list[str]]:
    """Chi ha nodi assegnati e quali, in ordine di nome.

    L'ordine e' alfabetico e non di apparizione perche' da qui escono le colonne
    della dashboard: con l'ordine di apparizione un nodo chiuso in mezzo alla
    lista rimescolava i colori delle persone da una resa alla successiva. Un
    nodo congiunto compare sotto tutte le sue persone.
    """
    mappa: dict[str, list[str]] = {}
    for node in data["nodes"]:
        for nome in owners_of(node):
            mappa.setdefault(nome, []).append(node["id"])
    return {nome: mappa[nome] for nome in sorted(mappa, key=chiave_nome)}


def squadre(data: dict) -> dict[tuple[str, ...], list[str]]:
    """Le combinazioni di due o piu' persone che almeno un nodo ha davvero, coi
    suoi nodi. Ordinate come i nomi che le compongono.

    Un nodo congiunto continua a comparire anche sotto ogni singola persona in
    owners(): la squadra non sostituisce le righe individuali, le affianca.
    Senza, il pannello mostra tre nomi e chi guarda non sa dire se lavorano
    insieme o su nodi diversi, che e' proprio l'informazione che il campo owner
    a vettore ha reso rappresentabile.
    """
    mappa: dict[tuple[str, ...], list[str]] = {}
    for node in data["nodes"]:
        nomi = tuple(owners_of(node))
        if len(nomi) > 1:
            mappa.setdefault(nomi, []).append(node["id"])
    return {nomi: mappa[nomi]
            for nomi in sorted(mappa, key=lambda gruppo: [chiave_nome(n) for n in gruppo])}


def unowned(data: dict) -> list[str]:
    return [n["id"] for n in data["nodes"] if not owners_of(n)]
