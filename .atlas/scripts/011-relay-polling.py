"""Il polling verso Telegram, deciso e mai scritto.

Si esegue con:  atlas exec .atlas/scripts/011-relay-polling.py

La decisione 5 del grilling (docs/atlas-relay-design.md §6-bis) stabilisce che e'
il relay a interrogare Telegram, non viceversa: niente hostname pubblico, niente
certificato, niente porta aperta. Il codice ereditato da D04 del grafo
260830-atlas-interactions fa pero' l'opposto, cioe' riceve su POST
/telegram/webhook. Il primo grafo del relay non copriva la conversione: e' un buco
di costruzione, trovato dal nodo F01 e registrato nella sua fog.
"""
from core import mutate

DOC = "docs/atlas-relay-design.md"


def run(g):
    mutate.add_branch(g, "G", "Polling verso Telegram", "#be123c")

    mutate.add_node(g, id="G01", branch="G", type="task", mode="AFK", model="claude",
        title="Interroga Telegram invece di aspettarlo",
        question="Scrivi il long polling verso getUpdates che sostituisce la ricezione via webhook, alimentando lo stesso gestore di eventi gia' scritto (relay/telegram_webhook.py, che resta come traduttore dell'update in evento minimo: cambia da dove arriva l'update, non cosa se ne fa). Tieni l'offset degli update gia' visti, cosi' un riavvio del servizio non rigioca quel che ha gia' consegnato, e conserva la deduplica per update_id che il webhook aveva. Sola stdlib: urllib, nessuna libreria Telegram. Il ciclo vive dentro il servizio, non e' un secondo processo.")
    mutate.add_node(g, id="G02", branch="G", type="task", mode="AFK", model="claude",
        title="Smonta l'ingresso pubblico che non serve piu'",
        question="Con il polling in servizio (G01), l'endpoint POST /telegram/webhook, il secret token dell'header, l'hostname HTTPS e il blocco Caddy dedicato non servono piu' a ricevere: toglili, insieme ai prerequisiti che li pretendevano e alla documentazione che li nomina (relay/README.md, %s dove parla di webhook). Attenzione a non buttare quel che il polling continua a usare, cioe' la traduzione dell'update in evento e la verifica di chi puo' entrare. Il servizio dopo questo nodo non deve avere nessuna porta raggiungibile da Internet: verificalo, non limitarti a dichiararlo." % DOC,
        blockedBy=["G01"])
    mutate.add_node(g, id="G03", branch="G", type="task", mode="AFK", model="claude",
        title="Rimetti in pari la messa in servizio",
        question="F01 aveva diagnosticato l'ambiente con il codice ancora a webhook. Rivedi quella diagnosi alla luce del polling (G01, G02): cosa serve davvero per mettere in servizio il relay, quali segreti, quale accesso alla macchina, e cosa non serve piu'. Aggiorna relay/README.md e la sezione della messa in servizio, senza inventare segreti e senza stamparne nessuno.",
        blockedBy=["G02"])
