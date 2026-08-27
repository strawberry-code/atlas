"""Serve la dashboard su un server locale: la rigenera quando il grafo cambia.

La dashboard resta un file che si apre da disco ('atlas render'): 'serve' e'
un'altra porta d'ingresso, che la tiene viva su http://127.0.0.1 e avverte la
pagina gia' aperta di ricaricarsi quando graph.json cambia. Il rendering e'
quello di render.build, riusato pari pari: qui si decide quando rifarlo
(confrontando l'mtime del grafo con quello dell'ultima generazione) e come
spingerlo al browser (un EventSource che riceve un evento 'reload').

Quando il lucchetto remoto e' attivo (lock.remote in config), la vista mostra
anche chi tiene cosa sulle altre macchine: i lucchetti arrivano da
remotelock.elenca() con un passo tutto loro, PASSO_REMOTO, piu' lento della
ronda sul grafo. Dentro la finestra il server non parla col remote, che sia per
una richiesta o per il filo di guardia: un ls-remote costa mezzo secondo e non
deve appendersi a ogni pagina servita.

Un solo filo di guardia fa la ronda sul grafo e annuncia ai collegati; le
richieste HTTP cascano sui thread del ThreadingHTTPServer. Niente dipendenze:
http.server, socketserver, threading e webbrowser sono tutti stdlib.
"""
from __future__ import annotations

import hashlib
import http.server
import threading
import time
import webbrowser

from . import render, remotelock
from .config import ConfigError, Graph
from .store import StateError, read_transaction
from .strings import t

# quanto spesso il filo di guardia controlla se il grafo e' cambiato (secondi)
INTERVALLO = 1.0

# fascia di porte usata per la porta deterministica (utente, lontana dai well-known)
_PORTA_MIN = 20000
_PORTA_RANGE = 20000

# quanto spesso si rileggono i lucchetti remoti (secondi). Un ls-remote costa
# ~0.5 s: il filo di guardia resta a 1 s per il grafo, i lucchetti remoti hanno
# un passo tutto loro, piu' lento, e dentro la finestra non si tocca il remote.
PASSO_REMOTO = 30.0

# iniettato prima di </body>: apre il canale SSE e ricarica la pagina su 'reload'
_RICARICA = (
    '<script>'
    '(function(){'
    'if(!window.EventSource)return;'
    'var es=new EventSource("/events");'
    'es.addEventListener("reload",function(){location.reload()});'
    '})();'
    '</script>'
)


class Dashboard:
    """L'HTML in memoria, rigenerato quando l'mtime di graph.json avanza oppure
    quando cambia la verita' remota dei lucchetti delle altre macchine."""

    def __init__(self, ref: Graph) -> None:
        self._ref = ref
        self._html: str | None = None
        self._mtime: float | None = None
        # I lucchetti remoti come li ha restituiti l'ultima elenca(): None finche'
        # non si e' letto nulla (o il lucchetto remoto e' spento), altrimenti la
        # lista degli Esito di questo grafo. L'errore di rete e' un flag a parte,
        # cosi' il dato a video (anche stantio) non viene buttato via.
        self._remoto: list[object] | None = None
        self._remoto_errore = False
        self._ultima_lettura = 0.0
        self._remoto_sporco = False       # una lettura remota nuova aspetta di entrare in pagina
        self._lucchetto = threading.Lock()

    def _mtime_grafo(self) -> float | None:
        try:
            return self._ref.json_path.stat().st_mtime
        except OSError:
            return None

    def aggiorna(self) -> bool:
        """Rigenera se serve: True se l'HTML e' stato rifatto.

        Due motivi per rifarlo: l'mtime del grafo avanza, oppure cambia la verita'
        remota (elenco o errore). Un grafo momentaneamente illeggibile non fa
        rigenerare, come prima: la pagina a video resta quella di prima."""
        with self._lucchetto:
            mtime = self._mtime_grafo()
            if mtime is None:
                return False
            if not self._remoto_sporco and self._html is not None and mtime <= self._mtime:
                return False
            with read_transaction(self._ref.json_path) as data:
                self._html = render.build(self._ref, data,
                                          remoto=self._remoto, remoto_errore=self._remoto_errore)
            self._mtime = mtime
            self._remoto_sporco = False
            return True

    def aggiorna_remoto(self) -> bool:
        """Rilegge i lucchetti remoti se e' il momento: True se la vista e' cambiata.

        Il passo e' PASSO_REMOTO: dentro la finestra non si tocca il remote, qualunque
        cosa chieda il resto del server. La lettura vera sta FUORI dal lock, perche'
        un ls-remote costa mezzo secondo e durante quello la pagina deve continuare
        a essere servita. Una lettura che fallisce non scarta il dato a video: si
        annota l'errore (e si rigenera per mostrarlo), poi si riprova solo al prossimo
        passo. Col lucchetto remoto spento non c'e' nulla da fare.
        """
        if not remotelock.attivo():
            return False
        adesso = time.time()
        with self._lucchetto:
            if adesso - self._ultima_lettura < PASSO_REMOTO:
                return False
            self._ultima_lettura = adesso
        try:
            letto = remotelock.elenca()          # fuori dal lock: la rete non ferma la pagina
        except Exception:
            letto = remotelock.Esito(remotelock.RETE)   # un trasporto che alza invece di rispondere
        with self._lucchetto:
            if isinstance(letto, list):
                # Solo i lucchetti di questo grafo: le ref remote sono <slug>/<id>,
                # e la dashboard di un grafo non deve mostrare i lucchetti di un altro.
                prefisso = self._ref.slug + "/"
                nuovo = sorted((e for e in letto if (e.nome or "").startswith(prefisso)),
                               key=lambda e: e.nome or "")
                cambiato = nuovo != self._remoto or self._remoto_errore
                self._remoto = nuovo
                self._remoto_errore = False
            else:
                cambiato = not self._remoto_errore    # errore ripetuto: niente da rifare
                self._remoto_errore = True
            if cambiato:
                self._remoto_sporco = True
            return cambiato

    def html(self) -> str:
        self.aggiorna()
        return self._html or ""


class Viewers:
    """I collegati a /events: un reload annunciato arriva a tutti."""

    def __init__(self) -> None:
        self._clienti: set[Handler] = set()
        self._lucchetto = threading.Lock()

    def registra(self, handler: Handler) -> None:
        with self._lucchetto:
            self._clienti.add(handler)

    def lascia(self, handler: Handler) -> None:
        with self._lucchetto:
            self._clienti.discard(handler)

    def annuncia(self) -> None:
        messaggio = b"event: reload\ndata: reload\n\n"
        with self._lucchetto:
            presenti = list(self._clienti)
        for cliente in presenti:
            try:
                cliente.wfile.write(messaggio)
                cliente.wfile.flush()
            except OSError:
                self.lascia(cliente)


class Handler(http.server.BaseHTTPRequestHandler):
    """La dashboard a /, il canale SSE a /events, nient'altro."""

    server_version = "AtlasServe/1"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._pagina()
        elif self.path == "/events":
            self._eventi()
        else:
            self.send_error(404)

    def _pagina(self) -> None:
        try:
            html = self.server.dash.html()
        except (ConfigError, StateError):
            self.send_error(503, t("serve.grafo_mancante"))   # grafo rotto: diagnosi, non traceback
            return
        if not html:
            self.send_error(503, t("serve.grafo_mancante"))
            return
        html = html.replace("</body>", _RICARICA + "</body>", 1)
        corpo = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(corpo)

    def _eventi(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b": connesso\n\n")
        self.wfile.flush()
        self.server.spettatori.registra(self)
        try:
            while not self.server.fermo.is_set():
                try:
                    self.wfile.write(b": battito\n\n")
                    self.wfile.flush()
                except OSError:
                    break
                self.server.fermo.wait(15)
        finally:
            self.server.spettatori.lascia(self)

    def log_message(self, *args) -> None:
        pass  # una dashboard personale non riempie il terminale di log


class Server(http.server.ThreadingHTTPServer):
    """Il server con lo stato condiviso: dashboard, spettatori, segnale di stop."""


def _watch(server: Server) -> None:
    """La ronda: rigenera quando il grafo cambia, rilegge i lucchetti remoti col
    loro passo, e avverte i collegati quando qualcosa di visto cambia."""
    while not server.fermo.is_set():
        try:
            cambiato = server.dash.aggiorna()
        except (ConfigError, StateError):
            cambiato = False            # grafo momentaneamente illeggibile: al giro dopo
        try:
            if server.dash.aggiorna_remoto():
                cambiato = True
        except Exception:
            pass                        # un trasporto che alza invece di rispondere: la ronda non muore
        if cambiato:
            server.spettatori.annuncia()
        server.fermo.wait(INTERVALLO)


def _porta_progetto(ref: Graph) -> int:
    """Porta deterministica per questo grafo: la stessa a ogni riavvio di
    'atlas serve', cosi' l'origine http non cambia e le preferenze salvate dal
    browser in localStorage (tema, vista) sopravvivono. Senza, la porta 0
    lasciava scegliere al sistema operativo: a ogni riavvio un'origine diversa,
    e il tema tornava a quello di sistema."""
    digest = hashlib.sha256(str(ref.dir.resolve()).encode("utf-8")).digest()
    return _PORTA_MIN + int.from_bytes(digest[:2], "big") % _PORTA_RANGE


def _apri(url: str) -> None:
    """Apre il browser di sistema, se c'e': la URL e' gia' stampata, e' un gesto di cortesia."""
    try:
        webbrowser.open(url)
    except Exception:
        pass


def cmd_serve(ref: Graph, args) -> int:
    """'atlas serve': tiene la dashboard viva su un server locale."""
    dash = Dashboard(ref)
    dash.aggiorna()                     # la prima pagina parte gia' fresca
    porta = args.port
    if not porta:
        porta = _porta_progetto(ref)
        try:
            server = Server(("127.0.0.1", porta), Handler)
        except OSError:
            print(t("serve.porta_occupata", porta=porta))
            server = Server(("127.0.0.1", 0), Handler)
    else:
        server = Server(("127.0.0.1", porta), Handler)
    server.dash = dash
    server.spettatori = Viewers()
    server.fermo = threading.Event()
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    print(t("serve.avviato", url=url, slug=ref.slug))
    guardia = threading.Thread(target=_watch, args=(server,), daemon=True)
    guardia.start()
    if args.apri:
        _apri(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.fermo.set()
        server.server_close()
    return 0
