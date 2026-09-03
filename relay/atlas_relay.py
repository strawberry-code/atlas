"""Servizio relay isolato (D02): process/health-check, il long polling verso
Telegram (G01, relay/telegram_polling.py, che alimenta lo stesso traduttore
di update di D04), l'endpoint SSE del tunnel client-relay (D03), il pairing
Telegram one-tap (D05), l'inoltro delle azioni Telegram al client (D06), lo
scambio callback_data <-> capability sotto il limite di 64 byte di Telegram
(D08, capability_store.StoreCapability), il freno automatico per
installazione oltre una soglia oraria di invii (C01, throttle.FrenoOrario),
l'elenco/distacco dei computer collegati a una chat (C02, devices.py), il
comando '/view' con la sua risposta binaria, foto o pagina alleggerita
(D02 del grafo 260902-atlas-relay, view_command.py e /tunnel/deliver-file),
l'avviso di fine servizio per protocollo vecchio (E02, protocol_watch.py),
mandato alla connessione del tunnel quando la versione dichiarata e' sotto
la soglia di deprecazione, e l'avviso 'qualcosa e' cambiato' fra installazioni
che condividono un progetto (E01, peers.py, /peers/notify).

Bind solo su ATLAS_RELAY_HOST (default 127.0.0.1). Il webhook Telegram (D04)
che pretendeva un hostname pubblico e un blocco Caddy dedicato e' stato
smontato da G02, ora che G01 interroga Telegram invece di aspettarlo: nessuna
porta di questo processo e' pensata per restare raggiungibile da Internet.
Porta e host restano le uniche leve di configurazione, cosi' il servizio resta
isolato per costruzione da bot WhenAGI e Claude Proxy, che girano su porte e
systemd unit proprie.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty
from urllib.parse import parse_qs, urlsplit

import capability_store
import devices
import pairing
import peers
import protocol_watch
import status_commands
import telegram_polling
import throttle
import tunnel
import view_command
from telegram_webhook import (GestoreWebhook, costruisci_gestore_da_ambiente,
                               costruisci_invia_bottoni, costruisci_invia_file,
                               costruisci_invia_messaggio, costruisci_modifica_messaggio)

HOST = os.environ.get("ATLAS_RELAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("ATLAS_RELAY_PORT", "8765"))
TUNNEL_PATH = "/tunnel"
TAP_RESULT_PATH = "/tunnel/tap-result"
DELIVER_PATH = "/tunnel/deliver"
DELIVER_FILE_PATH = "/tunnel/deliver-file"
PAIRING_PATH = "/pairing"
PEERS_NOTIFY_PATH = "/peers/notify"
INTERVALLO_BATTITO = 15.0   # stesso passo del canale SSE della dashboard (serve.py)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/healthz":
            corpo = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if urlsplit(self.path).path == TUNNEL_PATH:
            self._tunnel()
            return
        if urlsplit(self.path).path == PAIRING_PATH:
            self._pairing_stato()
            return
        self.send_response(404)
        self.end_headers()

    def _bearer_ok(self) -> bool:
        token_atteso: str | None = getattr(self.server, "tunnel_token", None)
        if not token_atteso:
            return False
        try:
            tunnel.verifica_bearer(self.headers.get("Authorization"), token_atteso)
        except tunnel.TunnelRejected:
            return False
        return True

    def _json(self, status: int, payload: dict) -> None:
        corpo = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _pairing_stato(self) -> None:
        """GET /pairing?code=...: il client (serve_pairing.py) lo interroga
        finche' l'utente non conferma su Telegram o il codice scade. Stesso
        bearer del tunnel (D01: un token per progetto, non uno specifico per
        feature): chi puo' aprire il tunnel puo' anche chiedere un pairing."""
        gestore: pairing.GestorePairing | None = getattr(self.server, "gestore_pairing", None)
        if gestore is None:
            self.send_response(404)
            self.end_headers()
            return
        if not self._bearer_ok():
            self.send_response(401)
            self.end_headers()
            return
        codice = (parse_qs(urlsplit(self.path).query).get("code") or [""])[0]
        if not codice:
            self.send_response(400)
            self.end_headers()
            return
        self._json(200, {"status": gestore.stato(codice)})

    def _pairing_richiedi(self) -> None:
        """POST /pairing {"installation": "<id>"}: un codice monouso fresco
        piu' il deep link t.me da aprire. 404 se il pairing non e' configurato
        in questo ambiente (TELEGRAM_BOT_TOKEN_REF/TELEGRAM_BOT_USERNAME
        mancanti), stesso principio del gate del bot Telegram (D04)."""
        gestore: pairing.GestorePairing | None = getattr(self.server, "gestore_pairing", None)
        username: str | None = getattr(self.server, "pairing_bot_username", None)
        if gestore is None or not username:
            self.send_response(404)
            self.end_headers()
            return
        if not self._bearer_ok():
            self.send_response(401)
            self.end_headers()
            return
        lunghezza = int(self.headers.get("Content-Length") or 0)
        corpo_richiesta = self.rfile.read(lunghezza) if lunghezza else b""
        try:
            corpo = json.loads(corpo_richiesta) if corpo_richiesta else {}
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        installation_id = corpo.get("installation") if isinstance(corpo, dict) else None
        if not isinstance(installation_id, str) or not installation_id:
            self.send_response(400)
            self.end_headers()
            return
        codice, scadenza = gestore.richiedi(installation_id)
        self._json(200, {"code": codice, "url": f"https://t.me/{username}?start={codice}",
                          "expiresAt": scadenza})

    def _peers_notify(self) -> None:
        """POST /peers/notify {"projectCode","installation"} (E01): un'
        installazione avvisa che ha appena chiuso un pezzo di un progetto
        condiviso. Il codice e' opaco (payload/core/project_code.py): il
        relay non impara ne' il nome ne' il contenuto del progetto, solo che
        due installazioni condividono lo stesso token. Stesso bearer del
        tunnel. 404 se il pairing non e' configurato in questo ambiente
        (nessun modo di avvisare comunque)."""
        avvisa: peers.AvvisoPeer | None = getattr(self.server, "avviso_peer", None)
        if avvisa is None:
            self.send_response(404)
            self.end_headers()
            return
        if not self._bearer_ok():
            self.send_response(401)
            self.end_headers()
            return
        lunghezza = int(self.headers.get("Content-Length") or 0)
        corpo_richiesta = self.rfile.read(lunghezza) if lunghezza else b""
        try:
            corpo = json.loads(corpo_richiesta) if corpo_richiesta else {}
        except json.JSONDecodeError:
            corpo = None
        project_code = corpo.get("projectCode") if isinstance(corpo, dict) else None
        installation_id = corpo.get("installation") if isinstance(corpo, dict) else None
        if (not isinstance(project_code, str) or not project_code
                or not isinstance(installation_id, str) or not installation_id):
            self.send_response(400)
            self.end_headers()
            return
        avvisa(project_code, installation_id)
        self._json(200, {"ok": True})

    def _tunnel(self) -> None:
        """GET /tunnel?installation=: lo stream SSE che il client (D03) tiene
        aperto. Autentica il bearer, registra la linea nel registro condiviso
        del server sotto l'installazione che l'ha aperta (A05) e la tiene
        viva finche' il client non cade o il servizio non si ferma: nessun
        polling, un solo socket."""
        registro: tunnel.RegistroTunnel | None = getattr(self.server, "registro_tunnel", None)
        token_atteso: str | None = getattr(self.server, "tunnel_token", None)
        if registro is None or not token_atteso:
            self.send_response(404)
            self.end_headers()
            return
        try:
            tunnel.verifica_bearer(self.headers.get("Authorization"), token_atteso)
        except tunnel.TunnelRejected:
            self.send_response(401)
            self.end_headers()
            return
        query = parse_qs(urlsplit(self.path).query)
        installation_id = (query.get("installation") or [""])[0]
        if not installation_id:
            self.send_response(400)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        coda = registro.connetti(installation_id)
        gestore_pairing: pairing.GestorePairing | None = getattr(self.server, "gestore_pairing", None)
        if gestore_pairing is not None:
            # C02: nessun battito dedicato, questa linea aperta e' gia' la
            # prova che l'installazione e' viva adesso (S7-ter/5).
            gestore_pairing.segna_vista(installation_id)
        avvisa_protocollo = getattr(self.server, "avvisa_protocollo", None)
        if avvisa_protocollo is not None:
            # E02: stesso punto di segna_vista sopra, la connessione del
            # tunnel e' il contatto piu' regolare che il relay ha con questa
            # installazione. 'X-Atlas-Protocol' (A01) manca su un client non
            # ancora aggiornato a questa modifica: None non avvisa mai.
            versione_grezza = self.headers.get(protocol_watch.INTESTAZIONE_PROTOCOLLO)
            try:
                versione_dichiarata = int(versione_grezza) if versione_grezza is not None else None
            except ValueError:
                versione_dichiarata = None
            avvisa_protocollo(installation_id, versione_dichiarata)
        try:
            while not self.server.fermo.is_set():
                try:
                    evento = coda.get(timeout=INTERVALLO_BATTITO)
                except Empty:
                    evento = None
                try:
                    if evento is None:
                        self.wfile.write(b": battito\n\n")
                    else:
                        corpo = json.dumps(evento).encode("utf-8")
                        self.wfile.write(b"event: tap\ndata: " + corpo + b"\n\n")
                    self.wfile.flush()
                except OSError:
                    break
        finally:
            registro.disconnetti(installation_id, coda)

    def _tap_result(self) -> None:
        """POST /tunnel/tap-result {"chatId", "messageId", "text"} (D06): il
        client, dopo aver risolto un'Interaction, chiede di aggiornare il
        messaggio Telegram con l'esito. Stesso bearer del tunnel (D01: chi
        puo' aprirlo puo' anche chiedere questo). 404 finche' il bot
        Telegram non e' configurato (nessun bot token per editMessageText)."""
        modifica = getattr(self.server, "modifica_messaggio", None)
        if modifica is None:
            self.send_response(404)
            self.end_headers()
            return
        if not self._bearer_ok():
            self.send_response(401)
            self.end_headers()
            return
        lunghezza = int(self.headers.get("Content-Length") or 0)
        corpo_richiesta = self.rfile.read(lunghezza) if lunghezza else b""
        try:
            corpo = json.loads(corpo_richiesta) if corpo_richiesta else {}
        except json.JSONDecodeError:
            corpo = None
        chat_id = corpo.get("chatId") if isinstance(corpo, dict) else None
        message_id = corpo.get("messageId") if isinstance(corpo, dict) else None
        testo = corpo.get("text") if isinstance(corpo, dict) else None
        if not isinstance(chat_id, int) or not isinstance(message_id, int) or not isinstance(testo, str):
            self.send_response(400)
            self.end_headers()
            return
        modifica(chat_id, message_id, testo)
        self._json(200, {"ok": True})

    def _tunnel_deliver(self) -> None:
        """POST /tunnel/deliver {"installation","text","buttons":[{"label","data"}]}
        (D07): il deliver iniziale di un'Interazione con un bottone per
        azione ammessa. Stesso bearer del tunnel. 404 se Telegram non e'
        configurato lato relay (nessun bot token: A01/D02 ancora chiusi),
        409 se l'installazione non e' appaiata a nessuna chat (il pairing
        A02 non ancora completato dall'utente), 429 se l'installazione ha
        superato la soglia oraria del freno automatico (C01), 502 se
        Telegram rifiuta l'invio.

        'data' qui e' ancora il capability token per intero (D01): il client
        non lo accorcia mai, non sa nulla di limiti Telegram. E' qui, appena
        prima di 'invia' (Telegram vero), che 'capability_store' (D08) lo
        scambia con l'identificativo corto che finisce davvero su
        callback_data, sotto il limite di 64 byte."""
        invia = getattr(self.server, "invia_bottoni", None)
        gestore_pairing: pairing.GestorePairing | None = getattr(self.server, "gestore_pairing", None)
        if invia is None or gestore_pairing is None:
            self.send_response(404)
            self.end_headers()
            return
        if not self._bearer_ok():
            self.send_response(401)
            self.end_headers()
            return
        lunghezza = int(self.headers.get("Content-Length") or 0)
        corpo_richiesta = self.rfile.read(lunghezza) if lunghezza else b""
        try:
            corpo = json.loads(corpo_richiesta) if corpo_richiesta else {}
        except json.JSONDecodeError:
            corpo = None
        installation_id = corpo.get("installation") if isinstance(corpo, dict) else None
        testo = corpo.get("text") if isinstance(corpo, dict) else None
        bottoni = corpo.get("buttons") if isinstance(corpo, dict) else None
        if (not isinstance(installation_id, str) or not isinstance(testo, str)
                or not isinstance(bottoni, list)
                or not all(isinstance(b, dict) and isinstance(b.get("label"), str)
                          and isinstance(b.get("data"), str) for b in bottoni)):
            self.send_response(400)
            self.end_headers()
            return
        chat_id = gestore_pairing.chat_id_di(installation_id)
        if chat_id is None:
            self.send_response(409)
            self.end_headers()
            return
        freno: throttle.FrenoOrario | None = getattr(self.server, "freno_orario", None)
        if freno is not None:
            esito_freno = freno.consenti(installation_id)
            if esito_freno != "ok":
                if esito_freno == "nuovo_blocco":
                    notifica_blocco = getattr(self.server, "notifica_blocco_freno", None)
                    if notifica_blocco is not None:
                        notifica_blocco(installation_id, chat_id)
                self.send_response(429)
                self.end_headers()
                return
        store: capability_store.StoreCapability | None = getattr(
            self.server, "capability_store", None)
        # D08: sul bottone Telegram non va il capability token (~270 byte,
        # oltre il limite di 64 di callback_data), va l'identificativo corto
        # che lo referenzia nello store del relay. Se lo store non e'
        # configurato (atlas_relay.main() lo crea sempre quando Telegram lo
        # e': solo i test che non gli badano lo lasciano assente) il dato
        # passa cosi' com'e', come prima di D08.
        coppie = [(b["label"], store.registra(b["data"]) if store is not None else b["data"])
                 for b in bottoni]
        try:
            invia(chat_id, testo, coppie)
        except (OSError, urllib.error.URLError):
            self.send_response(502)
            self.end_headers()
            return
        self._json(200, {"ok": True})

    def _tunnel_deliver_file(self) -> None:
        """POST /tunnel/deliver-file {"installation","filename","mime","kind",
        "content"} (D02): come /tunnel/deliver ma per la risposta di '/view',
        un file binario in base64 invece di testo e bottoni. Stesso bearer,
        stesso 409 se l'installazione non e' appaiata, stesso 429 sotto il
        freno automatico (C01): '/view' resta un invio verso la stessa chat,
        e la stessa soglia deve valere per non farla scavalcare da questa via."""
        invia = getattr(self.server, "invia_file", None)
        gestore_pairing: pairing.GestorePairing | None = getattr(self.server, "gestore_pairing", None)
        if invia is None or gestore_pairing is None:
            self.send_response(404)
            self.end_headers()
            return
        if not self._bearer_ok():
            self.send_response(401)
            self.end_headers()
            return
        lunghezza = int(self.headers.get("Content-Length") or 0)
        corpo_richiesta = self.rfile.read(lunghezza) if lunghezza else b""
        try:
            corpo = json.loads(corpo_richiesta) if corpo_richiesta else {}
        except json.JSONDecodeError:
            corpo = None
        installation_id = corpo.get("installation") if isinstance(corpo, dict) else None
        filename = corpo.get("filename") if isinstance(corpo, dict) else None
        mime = corpo.get("mime") if isinstance(corpo, dict) else None
        kind = corpo.get("kind") if isinstance(corpo, dict) else None
        contenuto_b64 = corpo.get("content") if isinstance(corpo, dict) else None
        if (not all(isinstance(v, str) and v for v in
                   (installation_id, filename, mime, kind, contenuto_b64))
                or kind not in ("photo", "document")):
            self.send_response(400)
            self.end_headers()
            return
        try:
            contenuto = base64.b64decode(contenuto_b64, validate=True)
        except binascii.Error:
            self.send_response(400)
            self.end_headers()
            return
        chat_id = gestore_pairing.chat_id_di(installation_id)
        if chat_id is None:
            self.send_response(409)
            self.end_headers()
            return
        freno: throttle.FrenoOrario | None = getattr(self.server, "freno_orario", None)
        if freno is not None:
            esito_freno = freno.consenti(installation_id)
            if esito_freno != "ok":
                if esito_freno == "nuovo_blocco":
                    notifica_blocco = getattr(self.server, "notifica_blocco_freno", None)
                    if notifica_blocco is not None:
                        notifica_blocco(installation_id, chat_id)
                self.send_response(429)
                self.end_headers()
                return
        try:
            invia(chat_id, filename, contenuto, mime, kind)
        except (OSError, urllib.error.URLError):
            self.send_response(502)
            self.end_headers()
            return
        self._json(200, {"ok": True})

    def do_POST(self) -> None:
        if urlsplit(self.path).path == TAP_RESULT_PATH:
            self._tap_result()
            return
        if urlsplit(self.path).path == DELIVER_PATH:
            self._tunnel_deliver()
            return
        if urlsplit(self.path).path == DELIVER_FILE_PATH:
            self._tunnel_deliver_file()
            return
        if urlsplit(self.path).path == PAIRING_PATH:
            self._pairing_richiedi()
            return
        if urlsplit(self.path).path == PEERS_NOTIFY_PATH:
            self._peers_notify()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args) -> None:
        pass  # niente rumore su stdout: il log del servizio lo tiene systemd/journald


class _RelayServer(ThreadingHTTPServer):
    gestore_webhook: GestoreWebhook | None = None
    tunnel_token: str | None = None
    registro_tunnel: tunnel.RegistroTunnel | None = None
    gestore_pairing: pairing.GestorePairing | None = None
    pairing_bot_username: str | None = None
    modifica_messaggio: object = None
    invia_bottoni: object = None
    invia_file: object = None
    capability_store: capability_store.StoreCapability | None = None
    freno_orario: throttle.FrenoOrario | None = None
    notifica_blocco_freno: object = None
    avvisa_protocollo: object = None
    avviso_peer: object = None
    fermo: threading.Event


def crea_server(host: str = HOST, port: int = PORT,
                 gestore_webhook: GestoreWebhook | None = None,
                 tunnel_token: str | None = None,
                 registro_tunnel: tunnel.RegistroTunnel | None = None,
                 gestore_pairing: pairing.GestorePairing | None = None,
                 pairing_bot_username: str | None = None,
                 modifica_messaggio: object = None,
                 invia_bottoni: object = None,
                 invia_file: object = None,
                 capability_store: capability_store.StoreCapability | None = None,
                 freno_orario: throttle.FrenoOrario | None = None,
                 notifica_blocco_freno: object = None,
                 avvisa_protocollo: object = None,
                 avviso_peer: object = None,
                 ) -> ThreadingHTTPServer:
    server = _RelayServer((host, port), Handler)
    server.gestore_webhook = gestore_webhook
    server.tunnel_token = tunnel_token
    server.registro_tunnel = registro_tunnel
    server.gestore_pairing = gestore_pairing
    server.pairing_bot_username = pairing_bot_username
    server.modifica_messaggio = modifica_messaggio
    server.invia_bottoni = invia_bottoni
    server.invia_file = invia_file
    server.capability_store = capability_store
    server.freno_orario = freno_orario
    server.notifica_blocco_freno = notifica_blocco_freno
    server.avvisa_protocollo = avvisa_protocollo
    server.avviso_peer = avviso_peer
    server.fermo = threading.Event()
    return server


def main() -> None:
    token = os.environ.get("ATLAS_RELAY_TOKEN_REF")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN_REF")
    gestore_pairing = pairing.costruisci_da_ambiente(os.environ)
    pairing_start = None
    admin_decision = None
    freno_orario = None
    notifica_blocco_freno = None
    avvisa_protocollo = None
    avviso_peer = None
    comando_dispositivi = None
    if gestore_pairing is not None:
        # A03: 'pairing_start' e 'admin_decision' condividono lo stesso store
        # e le stesse chiamate Telegram, ma sono due confini distinti verso
        # GestoreWebhook (uno per '/start <codice>', l'altro per il tap del
        # gestore su Approva/Rifiuta).
        invia_messaggio = costruisci_invia_messaggio(bot_token)
        invia_bottoni_admin = costruisci_invia_bottoni(bot_token)
        pairing_start = pairing.costruisci_pairing_start(
            gestore_pairing, invia_messaggio, invia_bottoni_admin)
        admin_decision_pairing = pairing.costruisci_admin_decision(
            gestore_pairing, invia_messaggio, costruisci_modifica_messaggio(bot_token))
        # C01: il freno automatico ha il suo prefisso di callback_data
        # ('gestore:sblocca:'/'utente:appello:'), distinto da quello del
        # pairing ('gestore:approva:'/'gestore:rifiuta:'): la combinazione
        # prova prima l'uno poi l'altro, un solo slot 'admin_decision' verso
        # GestoreWebhook come gia' faceva il solo pairing.
        freno_orario = throttle.FrenoOrario()
        notifica_blocco_freno = throttle.costruisci_notifica_blocco(
            gestore_pairing, invia_messaggio, invia_bottoni_admin)
        admin_decision_freno = throttle.costruisci_admin_decision(
            freno_orario, gestore_pairing, invia_messaggio, invia_bottoni_admin)
        # E02: un avviso per installazione per la vita del processo, mandato
        # alla connessione del tunnel (S7-ter/6) quando la versione dichiarata
        # e' sotto la soglia di deprecazione (protocol_watch, None di default:
        # nessun avviso finche' il gestore non la alza a mano).
        avvisa_protocollo = protocol_watch.costruisci_avviso(
            protocol_watch.AvvisoProtocollo(), gestore_pairing, invia_messaggio)
        # C02: '/computer' elenca le installazioni della chat che lo chiede,
        # 'utente:stacca:' e' il tap che ne dimentica una. Stesso slot
        # 'admin_decision' gia' condiviso da pairing e freno: e' un gesto
        # dell'utente sul proprio collegamento, non un potere del gestore.
        comando_dispositivi = devices.costruisci_comando(
            gestore_pairing, invia_messaggio, invia_bottoni_admin)
        admin_decision_dispositivi = devices.costruisci_decision(
            gestore_pairing, invia_messaggio, costruisci_modifica_messaggio(bot_token))
        # E01: il pari da avvisare si risolve con la stessa 'chat_id_di' del
        # deliver (D07), il registro e' un file a parte perche' la chiave e'
        # il codice opaco di progetto, non un'installazione o un codice di
        # pairing.
        registro_peer = peers.costruisci_da_ambiente(os.environ)
        avviso_peer = peers.costruisci_avviso(
            registro_peer, gestore_pairing.chat_id_di, invia_messaggio)

        def admin_decision(dato: str, chat_id: int, message_id: int) -> bool:
            return (admin_decision_pairing(dato, chat_id, message_id)
                    or admin_decision_freno(dato, chat_id, message_id)
                    or admin_decision_dispositivi(dato, chat_id, message_id))
    registro_tunnel = tunnel.RegistroTunnel() if token else None
    # D06/A05: instrada un tap gia' verificato dal webhook verso la sola linea
    # aperta dell'installazione che ha mandato la notifica, a nessun'altra.
    # 'installazioni_di' e' plurale (una chat puo' seguire piu' installazioni,
    # grilling 9): senza altro modo di sapere quale ha aperto questo preciso
    # messaggio, si sceglie la piu' di recente appaiata. Senza pairing o senza
    # tunnel il webhook usa il sink di default (CodaTap), come prima.
    def _installazione_di(chat_id: int) -> str | None:
        installazioni = gestore_pairing.installazioni_di(chat_id)
        return installazioni[0] if installazioni else None

    sink = (tunnel.costruisci_instradamento(_installazione_di, registro_tunnel)
            if gestore_pairing is not None and registro_tunnel is not None else None)
    # D01: gli stessi tre comandi di stato passano dalla stessa risoluzione
    # d'installazione del sink sopra, ma rispondono subito 'non in linea'
    # (S7-ter/2) quando il push non trova nessuna linea aperta (grilling 8),
    # invece di lasciare che il tap si perda in silenzio come fa un tap vero.
    comando_stato = (status_commands.costruisci_comando_stato(
                        _installazione_di, registro_tunnel.push, invia_messaggio)
                     if gestore_pairing is not None and registro_tunnel is not None else None)
    # D02: stessa risoluzione e stesso 'non in linea' di comando_stato sopra,
    # un comando a se' perche' risponde con un file, non con un messaggio.
    comando_view = (view_command.costruisci_comando_view(
                        _installazione_di, registro_tunnel.push, invia_messaggio)
                    if gestore_pairing is not None and registro_tunnel is not None else None)
    # D08: lo stesso store serve sia il deliver (registra il token, torna
    # l'id corto) sia il webhook (risolve l'id corto nel token): un bottone
    # su cui il bot non e' mai stato configurato non emette mai id da
    # risolvere, quindi lo store puo' esistere sempre, senza un gate suo.
    memoria_capability = capability_store.StoreCapability()
    server = crea_server(
        gestore_webhook=costruisci_gestore_da_ambiente(
            os.environ, pairing=gestore_pairing, sink=sink, pairing_start=pairing_start,
            capability_resolver=memoria_capability.preleva, admin_decision=admin_decision,
            dispositivi_comando=comando_dispositivi, comando_stato=comando_stato,
            comando_view=comando_view),
        tunnel_token=token,
        registro_tunnel=registro_tunnel,
        gestore_pairing=gestore_pairing,
        pairing_bot_username=os.environ.get("TELEGRAM_BOT_USERNAME"),
        modifica_messaggio=costruisci_modifica_messaggio(bot_token) if bot_token else None,
        invia_bottoni=costruisci_invia_bottoni(bot_token) if bot_token else None,
        invia_file=costruisci_invia_file(bot_token) if bot_token else None,
        capability_store=memoria_capability,
        freno_orario=freno_orario,
        notifica_blocco_freno=notifica_blocco_freno,
        avvisa_protocollo=avvisa_protocollo,
        avviso_peer=avviso_peer,
    )
    if server.gestore_webhook is not None:
        # G01: unica via d'ingresso degli update Telegram, dopo che G02 ha
        # smontato il webhook HTTPS. Il thread e' gia' demone e si ferma da
        # solo su server.fermo, che il finally sotto imposta comunque allo
        # shutdown del server HTTP.
        telegram_polling.avvia_poller_da_ambiente(
            os.environ, server.gestore_webhook.processa_update, server.fermo)
    try:
        server.serve_forever()
    finally:
        server.fermo.set()   # sblocca ogni _tunnel() ancora ferma su coda.get()
        server.server_close()


if __name__ == "__main__":
    main()
