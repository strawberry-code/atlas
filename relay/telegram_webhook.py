"""Adapter Telegram lato relay (D04): riceve il webhook HTTPS di Telegram,
verifica che sia davvero Telegram a chiamare, scarta gli utenti non ancora
associati a un progetto e rende idempotente ogni callback inline.

Non parla mai col ledger Atlas: quello resta un'esclusiva del client (D01).
Non decide nemmeno quale progetto risponde a un tap: si ferma al confine del
relay, passando un evento minimo a un sink iniettato (il tunnel di D03 verso
il client, o - nei test e finche' D03 non e' collegato - una coda in memoria).
Il payload che attraversa quel confine porta solo cio' che D06 deve poter
correlare a una capability: chat_id, message_id, callback_data/testo. Mai il
corpo completo dell'update Telegram, che puo' contenere campi non necessari
(nome, username, lingua del mittente, ...).

L'associazione chat -> progetto (PairingStore) e' un confine, non
un'implementazione: D05 costruisce il flusso one-tap che la popola davvero.
'MemoriaPairing' qui e' solo lo stub minimo, vuoto per costruzione, coerente
col fatto che finche' D05 non esiste nessuna chat e' associata a niente.
"""
from __future__ import annotations

import hmac
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from typing import Protocol


class WebhookRejected(ValueError):
    """La richiesta non e' un webhook Telegram autentico o valido."""


class UnpairedUser(ValueError):
    """Il chat Telegram non e' associato a nessun progetto Atlas."""


class PairingStore(Protocol):
    """Confine verso il pairing (D05): sa solo rispondere 'questa chat e'
    associata?'. D04 non decide come si diventa associati, solo che uno non
    associato e' rifiutato."""

    def is_paired(self, chat_id: int) -> bool: ...


class MemoriaPairing:
    """Store in memoria, vuoto per costruzione. Sostituito da un'implementazione
    persistente quando D05 costruisce il pairing one-tap: e' l'interfaccia che
    D04 fissa, non questa classe, il confine stabile fra i due nodi."""

    def __init__(self, chat_ids: Iterable[int] = ()) -> None:
        self._paired = set(chat_ids)

    def is_paired(self, chat_id: int) -> bool:
        return chat_id in self._paired

    def associa(self, chat_id: int) -> None:
        self._paired.add(chat_id)


class DedupCallback:
    """Insieme limitato di update_id gia' visti. Una redelivery Telegram dello
    stesso update (tipico se il relay non risponde entro il timeout) non deve
    attraversare il confine una seconda volta. Limitato per non crescere senza
    fine su un processo long-running: non serve precisione oltre la finestra
    di redelivery di Telegram, che si misura in minuti."""

    def __init__(self, capienza: int = 2048) -> None:
        self._capienza = capienza
        self._ordine: list[int] = []
        self._visti: set[int] = set()

    def gia_visto(self, update_id: int) -> bool:
        if update_id in self._visti:
            return True
        self._visti.add(update_id)
        self._ordine.append(update_id)
        if len(self._ordine) > self._capienza:
            scaduto = self._ordine.pop(0)
            self._visti.discard(scaduto)
        return False


class CodaTap:
    """Sink di default: coda in memoria degli eventi verificati, in attesa di
    attraversare il tunnel (D03) verso il client. Non persiste nulla, per
    costruzione: D01 esclude esplicitamente una coda di rimessaggio lato
    relay fra una disconnessione e l'altra del tunnel."""

    def __init__(self) -> None:
        self._eventi: list[dict] = []

    def __call__(self, evento: dict) -> None:
        self._eventi.append(evento)

    def preleva_tutti(self) -> list[dict]:
        eventi, self._eventi = self._eventi, []
        return eventi


AnswerCallback = Callable[[object], None]
Sink = Callable[[dict], None]
PairingStart = Callable[[str, int], None]


def verifica_segreto(header_segreto: str | None, atteso: str) -> None:
    """Confronta l'header X-Telegram-Bot-Api-Secret-Token (il meccanismo
    documentato da Telegram per provare che la chiamata viene davvero da loro,
    non un endpoint indovinato) con quanto configurato per questo bot.
    hmac.compare_digest per non aprire un confronto a tempo sul segreto."""
    if not header_segreto or not hmac.compare_digest(header_segreto, atteso):
        raise WebhookRejected("secret token Telegram assente o non valido")


def _decodifica(corpo: bytes) -> Mapping[str, object]:
    try:
        update = json.loads(corpo.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as errore:
        raise WebhookRejected("corpo non e' JSON valido") from errore
    if not isinstance(update, Mapping):
        raise WebhookRejected("corpo non e' un update Telegram")
    return update


def _estrai_evento(update: Mapping[str, object]) -> dict | None:
    """Riduce l'update Telegram al minimo che serve a valle. Nessun campo del
    payload originale sopravvive oltre questi."""
    callback = update.get("callback_query")
    if isinstance(callback, Mapping):
        messaggio = callback.get("message") if isinstance(callback.get("message"), Mapping) else {}
        chat = messaggio.get("chat") if isinstance(messaggio.get("chat"), Mapping) else {}
        return {
            "kind": "callback",
            "callback_query_id": callback.get("id"),
            "chat_id": chat.get("id"),
            "message_id": messaggio.get("message_id"),
            "callback_data": callback.get("data"),
        }
    messaggio = update.get("message")
    if isinstance(messaggio, Mapping):
        chat = messaggio.get("chat") if isinstance(messaggio.get("chat"), Mapping) else {}
        evento = {
            "kind": "message",
            "chat_id": chat.get("id"),
            "message_id": messaggio.get("message_id"),
        }
        testo = messaggio.get("text")
        if isinstance(testo, str):
            # solo per riconoscere '/start <codice>' (D05): un messaggio senza
            # comando di pairing non porta mai il testo oltre questo modulo.
            evento["text"] = testo
        return evento
    return None


def _codice_pairing(evento: Mapping[str, object]) -> str | None:
    """Il codice dopo un '/start ' in un messaggio, se c'e': None per
    qualunque altro messaggio, cosi' chi chiama sa se trattarlo come normale
    o come tentativo di pairing (D05)."""
    testo = evento.get("text")
    if not isinstance(testo, str) or not testo.startswith("/start"):
        return None
    codice = testo[len("/start"):].strip()
    return codice or None


class GestoreWebhook:
    """Punto unico d'ingresso del webhook: verifica, deduplica, filtra per
    associazione, poi passa l'evento minimo al sink. Solleva WebhookRejected o
    UnpairedUser; chi chiama (l'handler HTTP) decide lo status code, questa
    classe non conosce HTTP."""

    def __init__(self, segreto_atteso: str, pairing: PairingStore, sink: Sink,
                 answer_callback: AnswerCallback | None = None,
                 dedup: DedupCallback | None = None,
                 pairing_start: PairingStart | None = None) -> None:
        self._segreto_atteso = segreto_atteso
        self._pairing = pairing
        self._sink = sink
        self._answer_callback = answer_callback
        self._dedup = dedup or DedupCallback()
        self._pairing_start = pairing_start

    def gestisci(self, corpo: bytes, header_segreto: str | None) -> None:
        verifica_segreto(header_segreto, self._segreto_atteso)
        update = _decodifica(corpo)
        evento = _estrai_evento(update)
        if evento is None:
            return  # tipo di update che il relay non instrada (join, edit, ...)

        if evento["kind"] == "callback" and self._answer_callback is not None:
            # Obbligo dell'API Telegram, prima ancora di sapere se l'utente e'
            # associato: altrimenti il bottone resta "in caricamento" sul client.
            self._answer_callback(evento["callback_query_id"])

        update_id = update.get("update_id")
        if isinstance(update_id, int) and self._dedup.gia_visto(update_id):
            return  # redelivery: gia' risposto sopra, non riattraversa il confine

        chat_id = evento.get("chat_id")

        if evento["kind"] == "message":
            codice = _codice_pairing(evento)
            if codice is not None:
                # Un '/start <codice>' e' il pairing stesso (D05): per
                # costruzione arriva da una chat non ancora associata, quindi
                # non deve mai finire nel controllo 'is_paired' sotto, ne'
                # attraversare il confine verso il sink come fosse un tap.
                if self._pairing_start is not None and isinstance(chat_id, int):
                    self._pairing_start(codice, chat_id)
                return

        if not isinstance(chat_id, int) or not self._pairing.is_paired(chat_id):
            raise UnpairedUser("chat non associata a nessun progetto")

        self._sink(evento)


def _chiamata_telegram(bot_token: str, metodo: str, payload: Mapping[str, object],
                        opener=urllib.request.urlopen) -> None:
    richiesta = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/{metodo}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener(richiesta, timeout=10):
        pass


def costruisci_answer_callback(bot_token: str, opener=urllib.request.urlopen) -> AnswerCallback:
    def _answer(callback_query_id: object) -> None:
        try:
            _chiamata_telegram(bot_token, "answerCallbackQuery",
                                {"callback_query_id": callback_query_id}, opener)
        except (OSError, urllib.error.URLError):
            # Ack best-effort: Telegram irraggiungibile non deve bloccare la
            # pipeline, e l'eccezione di urllib porterebbe l'URL (quindi il
            # bot token) nel messaggio se lasciata risalire.
            pass
    return _answer


def costruisci_invia_messaggio(bot_token: str, opener=urllib.request.urlopen) -> Callable[[int, str], None]:
    """'sendMessage' generico: lo usa il pairing (D05) per confermare o
    rifiutare un '/start', stesso principio best-effort di
    costruisci_answer_callback (mai un traceback col bot token dentro)."""
    def _invia(chat_id: int, testo: str) -> None:
        try:
            _chiamata_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": testo}, opener)
        except (OSError, urllib.error.URLError):
            pass
    return _invia


def costruisci_modifica_messaggio(bot_token: str,
                                  opener=urllib.request.urlopen) -> Callable[[int, int, str], None]:
    """'editMessageText' (D06): il client, dopo aver risolto un'Interaction,
    chiede al relay di aggiornare il messaggio con l'esito. 'reply_markup'
    vuoto toglie i bottoni insieme al testo, cosi' un secondo tap sullo
    stesso messaggio non genera un altro evento da instradare. Stesso
    principio best-effort delle altre chiamate Telegram di questo modulo."""
    def _modifica(chat_id: int, message_id: int, testo: str) -> None:
        try:
            _chiamata_telegram(bot_token, "editMessageText", {
                "chat_id": chat_id, "message_id": message_id, "text": testo,
                "reply_markup": {"inline_keyboard": []},
            }, opener)
        except (OSError, urllib.error.URLError):
            pass
    return _modifica


PREREQUISITI = ["TELEGRAM_BOT_TOKEN_REF", "TELEGRAM_WEBHOOK_SECRET_REF"]


def costruisci_gestore_da_ambiente(env: Mapping[str, str], pairing: PairingStore | None = None,
                                    sink: Sink | None = None,
                                    pairing_start: PairingStart | None = None) -> GestoreWebhook | None:
    """None se mancano i prerequisiti Telegram (stesso gate di A01/D02: bot e
    segreti non ancora approvati in questo ambiente): il resto del relay
    (/healthz) continua a funzionare, l'avvio del servizio non si blocca per
    una feature non ancora sbloccata. 'pairing_start' arriva da chi assembla
    il servizio (atlas_relay.main): questo modulo fissa solo il confine
    (D04), non costruisce l'implementazione del pairing (D05, relay/pairing.py)."""
    if any(not env.get(nome) for nome in PREREQUISITI):
        return None
    return GestoreWebhook(
        segreto_atteso=env["TELEGRAM_WEBHOOK_SECRET_REF"],
        pairing=pairing if pairing is not None else MemoriaPairing(),
        sink=sink if sink is not None else CodaTap(),
        answer_callback=costruisci_answer_callback(env["TELEGRAM_BOT_TOKEN_REF"]),
        pairing_start=pairing_start,
    )
