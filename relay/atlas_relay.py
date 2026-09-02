"""Servizio relay isolato (D02): process/health-check, l'adapter webhook
Telegram (D04), l'endpoint SSE del tunnel client-relay (D03), il pairing
Telegram one-tap (D05) e l'inoltro delle azioni Telegram al client (D06).

Bind solo su ATLAS_RELAY_HOST (default 127.0.0.1): l'esposizione pubblica passa
da Caddy (Caddyfile.atlas-relay), mai da questo processo. Porta e host sono le
uniche leve di configurazione, cosi' il servizio resta isolato per costruzione
da bot WhenAGI e Claude Proxy, che girano su porte e systemd unit proprie.
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty
from urllib.parse import parse_qs, urlsplit

import pairing
import tunnel
from telegram_webhook import (GestoreWebhook, UnpairedUser, WebhookRejected,
                               costruisci_gestore_da_ambiente, costruisci_invia_messaggio,
                               costruisci_modifica_messaggio)

HOST = os.environ.get("ATLAS_RELAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("ATLAS_RELAY_PORT", "8765"))
TELEGRAM_WEBHOOK_PATH = "/telegram/webhook"
TUNNEL_PATH = "/tunnel"
TAP_RESULT_PATH = "/tunnel/tap-result"
PAIRING_PATH = "/pairing"
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
        """POST /pairing {"graph": "<slug>"}: un codice monouso fresco piu'
        il deep link t.me da aprire. 404 se il pairing non e' configurato in
        questo ambiente (TELEGRAM_BOT_TOKEN_REF/TELEGRAM_BOT_USERNAME
        mancanti), stesso principio del gate del webhook (D04)."""
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
        graph = corpo.get("graph") if isinstance(corpo, dict) else None
        if not isinstance(graph, str) or not graph:
            self.send_response(400)
            self.end_headers()
            return
        codice, scadenza = gestore.richiedi(graph)
        self._json(200, {"code": codice, "url": f"https://t.me/{username}?start={codice}",
                          "expiresAt": scadenza})

    def _tunnel(self) -> None:
        """GET /tunnel?graph=&runId=: lo stream SSE che il client (D03) tiene
        aperto. Autentica il bearer di progetto, registra la sessione nel
        registro condiviso del server e la tiene viva finche' il client non
        cade o il servizio non si ferma: nessun polling, un solo socket."""
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
        graph = (query.get("graph") or [""])[0]
        run_id = (query.get("runId") or [""])[0]
        if not graph or not run_id:
            self.send_response(400)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        coda = registro.connetti(graph, run_id)
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
            registro.disconnetti(graph, run_id, coda)

    def _tap_result(self) -> None:
        """POST /tunnel/tap-result {"chatId", "messageId", "text"} (D06): il
        client, dopo aver risolto un'Interaction, chiede di aggiornare il
        messaggio Telegram con l'esito. Stesso bearer del tunnel (D01: chi
        puo' aprirlo puo' anche chiedere questo). 404 finche' il webhook
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

    def do_POST(self) -> None:
        if urlsplit(self.path).path == TAP_RESULT_PATH:
            self._tap_result()
            return
        if urlsplit(self.path).path == PAIRING_PATH:
            self._pairing_richiedi()
            return
        gestore: GestoreWebhook | None = getattr(self.server, "gestore_webhook", None)
        if self.path != TELEGRAM_WEBHOOK_PATH or gestore is None:
            self.send_response(404)
            self.end_headers()
            return
        lunghezza = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(lunghezza) if lunghezza else b""
        header_segreto = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
        try:
            gestore.gestisci(corpo, header_segreto)
        except WebhookRejected:
            self.send_response(401)
            self.end_headers()
            return
        except UnpairedUser:
            pass  # 200 comunque: niente retry-storm Telegram, nessuna informazione all'esterno
        corpo_risposta = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(corpo_risposta)))
        self.end_headers()
        self.wfile.write(corpo_risposta)

    def log_message(self, *args) -> None:
        pass  # niente rumore su stdout: il log del servizio lo tiene systemd/journald


class _RelayServer(ThreadingHTTPServer):
    gestore_webhook: GestoreWebhook | None = None
    tunnel_token: str | None = None
    registro_tunnel: tunnel.RegistroTunnel | None = None
    gestore_pairing: pairing.GestorePairing | None = None
    pairing_bot_username: str | None = None
    modifica_messaggio: object = None
    fermo: threading.Event


def crea_server(host: str = HOST, port: int = PORT,
                 gestore_webhook: GestoreWebhook | None = None,
                 tunnel_token: str | None = None,
                 registro_tunnel: tunnel.RegistroTunnel | None = None,
                 gestore_pairing: pairing.GestorePairing | None = None,
                 pairing_bot_username: str | None = None,
                 modifica_messaggio: object = None) -> ThreadingHTTPServer:
    server = _RelayServer((host, port), Handler)
    server.gestore_webhook = gestore_webhook
    server.tunnel_token = tunnel_token
    server.registro_tunnel = registro_tunnel
    server.gestore_pairing = gestore_pairing
    server.pairing_bot_username = pairing_bot_username
    server.modifica_messaggio = modifica_messaggio
    server.fermo = threading.Event()
    return server


def main() -> None:
    token = os.environ.get("ATLAS_RELAY_TOKEN_REF")
    gestore_pairing = pairing.costruisci_da_ambiente(os.environ)
    pairing_start = None
    if gestore_pairing is not None:
        invia_messaggio = costruisci_invia_messaggio(os.environ["TELEGRAM_BOT_TOKEN_REF"])
        pairing_start = pairing.costruisci_pairing_start(gestore_pairing, invia_messaggio)
    registro_tunnel = tunnel.RegistroTunnel() if token else None
    # D06: instrada un tap gia' verificato dal webhook verso la sessione
    # (graph, runId) giusta solo se sappiamo sia a quale progetto appartiene
    # (pairing) sia dove spingerlo (un tunnel aperto). Senza uno dei due il
    # webhook usa il sink di default (CodaTap), come prima di questo nodo.
    sink = (tunnel.costruisci_instradamento(gestore_pairing.progetto_di, registro_tunnel)
            if gestore_pairing is not None and registro_tunnel is not None else None)
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN_REF")
    server = crea_server(
        gestore_webhook=costruisci_gestore_da_ambiente(
            os.environ, pairing=gestore_pairing, sink=sink, pairing_start=pairing_start),
        tunnel_token=token,
        registro_tunnel=registro_tunnel,
        gestore_pairing=gestore_pairing,
        pairing_bot_username=os.environ.get("TELEGRAM_BOT_USERNAME"),
        modifica_messaggio=costruisci_modifica_messaggio(bot_token) if bot_token else None,
    )
    try:
        server.serve_forever()
    finally:
        server.fermo.set()   # sblocca ogni _tunnel() ancora ferma su coda.get()
        server.server_close()


if __name__ == "__main__":
    main()
