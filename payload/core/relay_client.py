"""Lato client del tunnel D03: connessione uscente e resiliente al relay OCI
definito in D01. Solo trasporto: legge gli eventi (tap) che il relay spinge e
li passa a chi chiama, non tocca mai il ledger Atlas. Una disconnessione di
rete resta un fatto del trasporto, non del grafo: questo modulo non importa
interactions/run_state/mutate e non scrive nulla su disco, cosi' non puo'
inventare una chiusura ('run-stopped', una scadenza) che il lifecycle di A04
non ha deciso. Il tunnel puo' sparire e riapparire quante volte vuole finche'
'stop' non e' segnalato: l'unica fonte di verita' resta il grafo locale.

Trasporto: GET a lungo termine in stile SSE su '<base>/tunnel' (D01), identita'
di sessione (graph, runId) in query string, bearer ATLAS_RELAY_TOKEN_REF
nell'header Authorization. Nessun polling: una sola richiesta tenuta aperta e
riletta riga per riga; alla caduta (errore di trasporto o timeout di lettura,
oltre due battiti mancati del relay) backoff esponenziale con full jitter e
nuova connessione, all'infinito.
"""
from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from threading import Event
from urllib.parse import urlencode

ENV_URL = "RELAY_PUBLIC_URL"
ENV_HOSTNAME = "RELAY_HTTPS_HOSTNAME"
ENV_TOKEN = "ATLAS_RELAY_TOKEN_REF"

TIMEOUT_LETTURA = 20.0     # il relay manda un battito ogni 15s (INTERVALLO_BATTITO lato relay)
BACKOFF_BASE = 1.0
BACKOFF_FATTORE = 2.0
BACKOFF_CAP = 30.0

OnEvent = Callable[[dict], None]


class ConnessioneRelayRifiutata(RuntimeError):
    """Il relay ha risposto, ma non con 200: non e' un errore di trasporto da
    assorbire in silenzio quanto gli altri (es. 401 su un token scaduto)."""


@dataclass(frozen=True)
class TunnelConfig:
    base_url: str
    token: str

    def url_tunnel(self, graph: str, run_id: str) -> str:
        query = urlencode({"graph": graph, "runId": run_id})
        return f"{self.base_url.rstrip('/')}/tunnel?{query}"


def da_ambiente(env: Mapping[str, str]) -> TunnelConfig | None:
    """None se il relay non e' configurato per questo progetto: stesso gate di
    A01/D01, senza inventare un URL o un token di comodo."""
    base = env.get(ENV_URL) or (f"https://{env[ENV_HOSTNAME]}" if env.get(ENV_HOSTNAME) else None)
    token = env.get(ENV_TOKEN)
    if not base or not token:
        return None
    return TunnelConfig(base_url=base, token=token)


def _backoff(tentativo: int, rand: Callable[[], float] = random.random) -> float:
    """Full jitter (AWS): cresce esponenzialmente ma resta uniforme fra 0 e il
    tetto del tentativo, cosi' tante riconnessioni non ripartono mai in coro."""
    tetto = min(BACKOFF_CAP, BACKOFF_BASE * BACKOFF_FATTORE ** tentativo)
    return tetto * rand()


def _decodifica_sse(risposta) -> Iterator[dict]:
    """Un frame per 'yield': solo quelli con almeno una riga 'data:'. Righe
    ':...' (i battiti) e frame senza dati sono commenti, si scartano senza
    diventare un evento vuoto."""
    dato: list[str] = []
    while True:
        riga = risposta.readline()
        if not riga:
            return  # stream chiuso dal relay: fine pulita, si riconnette fuori
        riga = riga.decode("utf-8", "replace").rstrip("\r\n")
        if riga.startswith(":"):
            continue
        if riga == "":
            if dato:
                testo, dato = "\n".join(dato), []
                try:
                    yield json.loads(testo)
                except json.JSONDecodeError:
                    continue  # frame malformato: si ignora, non e' un guasto di trasporto
            continue
        if riga.startswith("data:"):
            dato.append(riga[len("data:"):].lstrip(" "))
        # altre righe (es. 'event: tap') non servono: il payload JSON basta


def _connetti_e_consuma(config: TunnelConfig, graph: str, run_id: str, on_event: OnEvent,
                        stop: Event, opener) -> None:
    richiesta = urllib.request.Request(
        config.url_tunnel(graph, run_id),
        headers={"Authorization": f"Bearer {config.token}"},
    )
    with opener(richiesta, timeout=TIMEOUT_LETTURA) as risposta:
        if risposta.status != 200:
            raise ConnessioneRelayRifiutata(f"tunnel rifiutato dal relay: HTTP {risposta.status}")
        for evento in _decodifica_sse(risposta):
            if stop.is_set():
                return
            try:
                on_event(evento)
            except Exception:
                continue  # un evento che chi chiama non ha saputo gestire non abbatte il tunnel


def aggiorna_messaggio(config: TunnelConfig, chat_id: int, message_id: int, testo: str,
                       opener=urllib.request.urlopen) -> None:
    """POST '<base>/tunnel/tap-result' (D06): chiede al relay di aggiornare
    un messaggio Telegram con l'esito di un tap gia' risolto sul ledger. Solo
    trasporto, come il resto del modulo: la transazione su Atlas e' gia'
    commessa quando questa funzione viene chiamata, quindi un relay
    irraggiungibile qui e' un fatto del canale Telegram, non del grafo, e si
    assorbe in silenzio (stesso stile best-effort delle chiamate dirette a
    Telegram in relay/telegram_webhook.py)."""
    corpo = json.dumps({"chatId": chat_id, "messageId": message_id, "text": testo}).encode("utf-8")
    richiesta = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/tunnel/tap-result",
        data=corpo, method="POST",
        headers={"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"},
    )
    try:
        with opener(richiesta, timeout=10):
            pass
    except (OSError, urllib.error.URLError):
        pass


def invia_messaggio(config: TunnelConfig, graph: str, testo: str, bottoni: list[tuple[str, str]],
                    opener=urllib.request.urlopen) -> None:
    """POST '<base>/tunnel/deliver' (D07): il deliver iniziale di
    un'Interazione aperta, un bottone per azione ammessa. A differenza di
    aggiorna_messaggio questa chiamata NON assorbe il guasto: la consegna non
    e' ancora avvenuta, quindi un relay irraggiungibile, non deployato o un
    progetto non ancora appaiato (D05) devono risalire a notify.dispatch
    (C01), che li registra nel ledger di consegna e decide se ritentare."""
    corpo = json.dumps({
        "graph": graph, "text": testo,
        "buttons": [{"label": etichetta, "data": dato} for etichetta, dato in bottoni],
    }).encode("utf-8")
    richiesta = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/tunnel/deliver",
        data=corpo, method="POST",
        headers={"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"},
    )
    with opener(richiesta, timeout=10) as risposta:
        if risposta.status != 200:
            raise ConnessioneRelayRifiutata(f"deliver rifiutato dal relay: HTTP {risposta.status}")


def esegui(config: TunnelConfig, graph: str, run_id: str, on_event: OnEvent, stop: Event,
          opener=urllib.request.urlopen, rand: Callable[[], float] = random.random,
          wait: Callable[[float], None] | None = None) -> None:
    """Il ciclo di vita del tunnel: connette, consuma, riconnette all'infinito.

    Non solleva mai per un guasto di trasporto: lo assorbe e riprova con
    backoff. L'unico modo per uscire e' che 'stop' sia gia' segnalato
    all'inizio di un giro. Pensato per girare nel suo thread: il chiamante
    decide quando fermarlo segnalando 'stop'.
    """
    attesa = wait or stop.wait
    tentativo = 0
    while not stop.is_set():
        try:
            _connetti_e_consuma(config, graph, run_id, on_event, stop, opener)
            tentativo = 0   # il relay ha accettato la connessione: si riparte da capo
        except (OSError, urllib.error.URLError, ConnessioneRelayRifiutata, TimeoutError):
            pass
        if stop.is_set():
            return
        attesa(_backoff(tentativo, rand))
        tentativo += 1
