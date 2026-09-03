"""Adapter Telegram lato relay (D04): traduce un update Telegram in evento
minimo, scarta gli utenti non ancora associati a un progetto e rende
idempotente ogni callback inline. 'GestoreWebhook.processa_update' e' il
punto unico d'ingresso, alimentato dal long polling verso getUpdates
(G02, relay/telegram_polling.py): riceve un update gia' decodificato da
Telegram stesso, senza nessun segreto da verificare, perche' e' questo
processo a chiamare Telegram e non il contrario. Il webhook HTTPS che
questo modulo esponeva (D04) e' stato smontato da G02 insieme al segreto
del suo header: nessuna porta di questo servizio deve restare raggiungibile
da Internet.

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

Il 'callback_data' che entra da questo modulo (D08) e' un identificativo
corto emesso da 'capability_store.StoreCapability' al momento del deliver,
non il capability token: pesa troppo per il limite di 64 byte di Telegram.
'GestoreWebhook' lo risolve nel token vero appena prima del sink, tramite
'capability_resolver' iniettato: questo modulo continua a non conoscere il
contenuto della capability, solo il suo trasporto opaco.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Mapping
from typing import Protocol


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
PairingStart = Callable[[str, int, "str | None"], None]
CapabilityResolver = Callable[[str], str | None]
AdminDecision = Callable[[str, int, int], bool]
DispositiviComando = Callable[[int], None]
ComandoStato = Callable[[str, int], bool]
ComandoView = Callable[[str, int], bool]

COMANDO_DISPOSITIVI = "/computer"


def _nome_da(messaggio: Mapping[str, object]) -> str | None:
    """Il nome Telegram di chi ha mandato il messaggio (S11/3: al gestore
    arriva il nome di chi chiede di entrare): username se c'e', altrimenti il
    nome proprio. None se il campo 'from' manca o non porta nessuno dei due."""
    mittente = messaggio.get("from")
    if not isinstance(mittente, Mapping):
        return None
    username = mittente.get("username")
    if isinstance(username, str) and username:
        return f"@{username}"
    nome = mittente.get("first_name")
    return nome if isinstance(nome, str) and nome else None


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
            if testo.startswith("/start"):
                # il nome serve solo qui (A03, cancello d'ingresso): ogni
                # altro messaggio resta ridotto a chat/message id come prima.
                evento["from_nome"] = _nome_da(messaggio)
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
    """Punto unico d'ingresso degli update Telegram: deduplica, filtra per
    associazione, poi passa l'evento minimo al sink. Solleva UnpairedUser;
    chi chiama (il long polling di relay/telegram_polling.py) decide cosa
    farne, questa classe non conosce il trasporto.

    'capability_resolver' (D08) e' l'unico punto in cui il callback_data che
    Telegram consegna, l'identificativo corto emesso da 'capability_store.
    StoreCapability' al deliver, torna a essere il capability token opaco che
    D06 sa verificare: se None (non ancora configurato, o test che non ne
    hanno bisogno) il campo attraversa questa classe cosi' com'e', come
    prima di D08. Un identificativo che il resolver non sa risolvere non
    raggiunge il sink: stesso 'nessuna traccia' di un token invalido scartato
    oggi da 'payload/core/capability.py', un passo prima.

    'admin_decision' (A03) e' lo stesso genere di confine per il tap del
    gestore su 'Approva'/'Rifiuta' di un ingresso: torna True se il
    callback_data era per lui (gestito, a prescindere dall'esito), False se
    non lo riconosce. Non tocca mai il sink ne' 'is_paired': il gestore
    decide un ingresso, non manda un tap di grafo.

    'dispositivi_comando' (C02) e' lo stesso genere di confine di
    'pairing_start' per '/computer': una chat elenca le proprie
    installazioni a prescindere dall'essere gia' associata (zero
    installazioni e' una risposta legittima, non un errore), quindi va
    riconosciuto prima del cancello 'is_paired' esattamente come '/start'.
    Il tap 'Stacca' che ne segue e' invece un callback qualunque e passa dal
    solito 'admin_decision', come gia' fa 'utente:appello:' (C01).

    'comando_stato' (D01) e' invece dopo il cancello 'is_paired': i tre
    comandi di stato rispondono con cio' che gira su un'installazione, quindi
    hanno senso solo per una chat gia' associata a qualcuna. Vero se il testo
    era uno dei tre comandi (D01 lo consegna gia' risolto, o dice subito che
    il computer non e' in linea): ferma lo smistamento qui, come
    'admin_decision' per un callback riconosciuto. Un messaggio che non e' uno
    dei tre comandi prosegue verso il sink come ogni altro messaggio, invariato."""

    def __init__(self, pairing: PairingStore, sink: Sink,
                 answer_callback: AnswerCallback | None = None,
                 dedup: DedupCallback | None = None,
                 pairing_start: PairingStart | None = None,
                 capability_resolver: CapabilityResolver | None = None,
                 admin_decision: AdminDecision | None = None,
                 dispositivi_comando: DispositiviComando | None = None,
                 comando_stato: ComandoStato | None = None,
                 comando_view: ComandoView | None = None) -> None:
        self._pairing = pairing
        self._sink = sink
        self._answer_callback = answer_callback
        self._dedup = dedup or DedupCallback()
        self._pairing_start = pairing_start
        self._capability_resolver = capability_resolver
        self._admin_decision = admin_decision
        self._dispositivi_comando = dispositivi_comando
        self._comando_stato = comando_stato
        self._comando_view = comando_view

    def processa_update(self, update: Mapping[str, object]) -> None:
        """Il traduttore vero e proprio: il long polling di
        relay/telegram_polling.py ci arriva con un update gia' decodificato
        da Telegram stesso, senza nessun segreto da verificare perche' e'
        questo processo a chiamare Telegram, non il contrario (il webhook
        HTTPS che verificava un header di segreto e' stato smontato da G02)."""
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
                    self._pairing_start(codice, chat_id, evento.get("from_nome"))
                return
            if (evento.get("text") == COMANDO_DISPOSITIVI and self._dispositivi_comando is not None
                    and isinstance(chat_id, int)):
                # C02: zero installazioni e' una risposta legittima quanto
                # una lista piena, quindi anche questo comando precede
                # 'is_paired' invece di dipendere da un'associazione gia'
                # esistente.
                self._dispositivi_comando(chat_id)
                return

        if evento["kind"] == "callback" and self._admin_decision is not None:
            # A03: il tap del gestore su 'Approva'/'Rifiuta' non e' un tap di
            # grafo, e il gestore non e' un'installazione associata: va
            # riconosciuto e assorbito qui, prima del cancello 'is_paired'.
            dato = evento.get("callback_data")
            message_id = evento.get("message_id")
            if (isinstance(dato, str) and isinstance(chat_id, int) and isinstance(message_id, int)
                    and self._admin_decision(dato, chat_id, message_id)):
                return

        if not isinstance(chat_id, int) or not self._pairing.is_paired(chat_id):
            raise UnpairedUser("chat non associata a nessun progetto")

        if evento["kind"] == "message" and self._comando_stato is not None:
            # D01: i tre comandi di stato si fermano qui, gestiti o no (il
            # 'non in linea' e' gia' risposto dentro 'comando_stato' stesso).
            # Un testo che non e' uno dei tre torna False e prosegue sotto.
            testo = evento.get("text")
            if isinstance(testo, str) and self._comando_stato(testo, chat_id):
                return

        if evento["kind"] == "message" and self._comando_view is not None:
            # D02: stesso principio di comando_stato sopra, un comando a se'
            # perche' la sua risposta e' un file, non un messaggio.
            testo = evento.get("text")
            if isinstance(testo, str) and self._comando_view(testo, chat_id):
                return

        if evento["kind"] == "callback" and self._capability_resolver is not None:
            # D08: il callback_data che Telegram ha appena consegnato e'
            # l'identificativo corto emesso al deliver, non il capability
            # token. Lo risolviamo qui, l'ultimo passo prima del sink: un
            # identificativo sconosciuto, scaduto o gia' consumato non
            # produce nulla da risolvere, e il tap si scarta qui, prima di
            # attraversare il tunnel verso il client.
            token = self._capability_resolver(evento.get("callback_data"))
            if token is None:
                return
            evento = {**evento, "callback_data": token}

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


def costruisci_invia_bottoni(bot_token: str,
                             opener=urllib.request.urlopen) -> Callable[[int, str, list], None]:
    """'sendMessage' con inline keyboard (D07): il deliver iniziale di
    un'Interazione, un bottone per azione ammessa. A differenza delle altre
    chiamate Telegram di questo modulo NON assorbe il guasto: qui il
    fallimento e' il primo tentativo di consegna, non l'effetto collaterale
    di una transazione Atlas gia' commessa, quindi deve risalire al
    chiamante (l'handler HTTP del relay) perche' il client lo registri nel
    ledger di consegna (C01) invece di credere arrivata una notifica che non
    lo e' mai stata."""
    def _invia(chat_id: int, testo: str, bottoni: list[tuple[str, str]]) -> None:
        tastiera = {"inline_keyboard": [[{"text": etichetta, "callback_data": dato}]
                                        for etichetta, dato in bottoni]}
        _chiamata_telegram(bot_token, "sendMessage",
                            {"chat_id": chat_id, "text": testo, "reply_markup": tastiera}, opener)
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


def _multipart(campi: Mapping[str, str], campo_file: str, filename: str,
               content: bytes, mime: str) -> tuple[bytes, str]:
    """Corpo multipart/form-data a mano: e' l'unica chiamata di questo modulo
    che porta bytes, non JSON, perche' l'API Telegram non accetta un upload
    per valore dentro un campo JSON. Nessuna libreria: la stdlib non ha un
    encoder multipart pronto, e per un solo campo file non vale la pena
    importarne uno di terze parti."""
    boundary = f"atlas-view-{uuid.uuid4().hex}"
    parti = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{chiave}"\r\n\r\n{valore}\r\n'
        .encode("utf-8")
        for chiave, valore in campi.items()
    ]
    parti.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{campo_file}"; '
        f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8")
        + content + b"\r\n"
    )
    parti.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parti), boundary


def costruisci_invia_file(bot_token: str, opener=urllib.request.urlopen
                          ) -> Callable[[int, str, bytes, str, str], None]:
    """'sendPhoto'/'sendDocument' (D02): la risposta di '/view'. A differenza
    delle altre chiamate Telegram di questo modulo non assorbe il guasto,
    stesso principio di costruisci_invia_bottoni: la consegna del file e' il
    primo tentativo, non l'effetto collaterale di una transazione gia'
    commessa sul ledger."""
    def _invia(chat_id: int, filename: str, content: bytes, mime: str, kind: str) -> None:
        metodo, campo = ("sendPhoto", "photo") if kind == "photo" else ("sendDocument", "document")
        corpo, boundary = _multipart({"chat_id": str(chat_id)}, campo, filename, content, mime)
        richiesta = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/{metodo}",
            data=corpo, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with opener(richiesta, timeout=20):
            pass
    return _invia


PREREQUISITI = ["TELEGRAM_BOT_TOKEN_REF"]


def costruisci_gestore_da_ambiente(env: Mapping[str, str], pairing: PairingStore | None = None,
                                    sink: Sink | None = None,
                                    pairing_start: PairingStart | None = None,
                                    capability_resolver: CapabilityResolver | None = None,
                                    admin_decision: AdminDecision | None = None,
                                    dispositivi_comando: DispositiviComando | None = None,
                                    comando_stato: ComandoStato | None = None,
                                    comando_view: ComandoView | None = None
                                    ) -> GestoreWebhook | None:
    """None se manca il prerequisito Telegram (stesso gate di A01/D02: bot non
    ancora approvato in questo ambiente): il resto del relay (/healthz)
    continua a funzionare, l'avvio del servizio non si blocca per una feature
    non ancora sbloccata. 'pairing_start' arriva da chi assembla il servizio
    (atlas_relay.main): questo modulo fissa solo il confine (D04), non
    costruisce l'implementazione del pairing (D05, relay/pairing.py).
    'capability_resolver' e' lo stesso principio per D08: qui si fissa solo
    il confine, 'capability_store.StoreCapability.preleva' e' l'implementazione
    che atlas_relay.main() costruisce e condivide con l'endpoint di deliver."""
    if any(not env.get(nome) for nome in PREREQUISITI):
        return None
    return GestoreWebhook(
        pairing=pairing if pairing is not None else MemoriaPairing(),
        sink=sink if sink is not None else CodaTap(),
        answer_callback=costruisci_answer_callback(env["TELEGRAM_BOT_TOKEN_REF"]),
        pairing_start=pairing_start,
        capability_resolver=capability_resolver,
        admin_decision=admin_decision,
        dispositivi_comando=dispositivi_comando,
        comando_stato=comando_stato,
        comando_view=comando_view,
    )
