"""Test del lato client del tunnel D03: config da ambiente, framing SSE,
backoff con jitter, e il ciclo di riconnessione, senza rete vera (opener
sempre iniettato) tranne un giro end-to-end contro il vero relay di D02/D04.
"""
from __future__ import annotations

import ast
import io
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

from core import relay_client
import atlas_relay
import tunnel as relay_tunnel

TOKEN = "il-bearer-del-tunnel"


class ConfigDaAmbiente(unittest.TestCase):
    def test_none_senza_url_ne_hostname(self):
        self.assertIsNone(relay_client.da_ambiente({"ATLAS_RELAY_TOKEN_REF": TOKEN}))

    def test_none_senza_token(self):
        self.assertIsNone(relay_client.da_ambiente({"RELAY_PUBLIC_URL": "https://relay.test"}))

    def test_url_esplicito_ha_precedenza_sull_hostname(self):
        config = relay_client.da_ambiente({
            "RELAY_PUBLIC_URL": "https://relay.test",
            "RELAY_HTTPS_HOSTNAME": "altro.test",
            "ATLAS_RELAY_TOKEN_REF": TOKEN,
        })
        self.assertEqual(config.base_url, "https://relay.test")

    def test_hostname_costruisce_url_https(self):
        config = relay_client.da_ambiente({
            "RELAY_HTTPS_HOSTNAME": "relay.test",
            "ATLAS_RELAY_TOKEN_REF": TOKEN,
        })
        self.assertEqual(config.base_url, "https://relay.test")

    def test_url_tunnel_porta_identita_di_sessione_in_query(self):
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)
        url = config.url_tunnel("mio-grafo", "run123")
        self.assertIn("graph=mio-grafo", url)
        self.assertIn("runId=run123", url)
        self.assertTrue(url.startswith("https://relay.test/tunnel?"))


class DecodificaSSE(unittest.TestCase):
    def _righe(self, testo: str):
        return io.BytesIO(testo.encode("utf-8"))

    def test_un_frame_dati_diventa_un_evento(self):
        eventi = list(relay_client._decodifica_sse(
            self._righe('event: tap\ndata: {"a": 1}\n\n')))
        self.assertEqual(eventi, [{"a": 1}])

    def test_battiti_e_commenti_non_producono_eventi(self):
        eventi = list(relay_client._decodifica_sse(self._righe(": battito\n\n: battito\n\n")))
        self.assertEqual(eventi, [])

    def test_piu_frame_in_sequenza(self):
        eventi = list(relay_client._decodifica_sse(
            self._righe('data: {"a": 1}\n\ndata: {"a": 2}\n\n')))
        self.assertEqual(eventi, [{"a": 1}, {"a": 2}])

    def test_frame_malformato_ignorato_non_ferma_il_flusso(self):
        eventi = list(relay_client._decodifica_sse(
            self._righe('data: non-json\n\ndata: {"a": 1}\n\n')))
        self.assertEqual(eventi, [{"a": 1}])


class Backoff(unittest.TestCase):
    def test_cresce_e_resta_sotto_il_tetto(self):
        valori = [relay_client._backoff(t, rand=lambda: 1.0) for t in range(8)]
        self.assertEqual(valori, sorted(valori))
        self.assertTrue(all(v <= relay_client.BACKOFF_CAP for v in valori))
        self.assertEqual(valori[-1], relay_client.BACKOFF_CAP)

    def test_jitter_pieno_puo_valere_zero(self):
        self.assertEqual(relay_client._backoff(3, rand=lambda: 0.0), 0.0)


class _RispostaVuota:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class AggiornaMessaggio(unittest.TestCase):
    """POST '<base>/tunnel/tap-result' (D06): la meta' outbound del tunnel
    che chiede al relay di aggiornare un messaggio Telegram gia' inviato."""

    def test_posta_bearer_e_corpo_corretti(self):
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)
        richieste = []

        def opener(richiesta, timeout=None):
            richieste.append(richiesta)
            return _RispostaVuota()

        relay_client.aggiorna_messaggio(config, 42, 7, "Fatto: Conferma.", opener=opener)
        self.assertEqual(len(richieste), 1)
        richiesta = richieste[0]
        self.assertEqual(richiesta.full_url, "https://relay.test/tunnel/tap-result")
        self.assertEqual(richiesta.get_header("Authorization"), f"Bearer {TOKEN}")
        import json as _json
        self.assertEqual(_json.loads(richiesta.data),
                         {"chatId": 42, "messageId": 7, "text": "Fatto: Conferma."})

    def test_relay_irraggiungibile_non_solleva(self):
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)

        def opener(richiesta, timeout=None):
            raise OSError("rete giu'")

        relay_client.aggiorna_messaggio(config, 1, 1, "x", opener=opener)  # non solleva


class FakeRisposta:
    def __init__(self, status: int, corpo: bytes):
        self.status = status
        self._buffer = io.BytesIO(corpo)

    def readline(self):
        return self._buffer.readline()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class CicloRiconnessione(unittest.TestCase):
    def test_evento_arriva_dopo_un_guasto_di_trasporto(self):
        """Prima richiesta: la rete cade (OSError). Seconda: il relay risponde
        con un evento. Il ciclo deve assorbire il primo guasto, aspettare col
        backoff iniettato, riconnettersi e consegnare l'evento."""
        tentativi = []

        def opener(richiesta, timeout):
            tentativi.append(richiesta)
            if len(tentativi) == 1:
                raise OSError("connessione rifiutata")
            return FakeRisposta(200, b'data: {"tap": true}\n\n')

        ricevuti = []
        stop = threading.Event()
        attese = []

        def wait(secondi):
            attese.append(secondi)

        def on_event(evento):
            ricevuti.append(evento)
            stop.set()   # l'evento e' arrivato: un solo giro di riconnessione basta al test

        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)
        relay_client.esegui(config, "grafo", "run1", on_event, stop,
                            opener=opener, rand=lambda: 0.0, wait=wait)

        self.assertEqual(ricevuti, [{"tap": True}])
        self.assertEqual(len(tentativi), 2)
        self.assertEqual(len(attese), 1)

    def test_stop_gia_segnalato_non_apre_nessuna_connessione(self):
        stop = threading.Event()
        stop.set()
        chiamato = []
        relay_client.esegui(relay_client.TunnelConfig("https://relay.test", TOKEN),
                            "grafo", "run1", chiamato.append, stop,
                            opener=lambda *a, **k: (_ for _ in ()).throw(AssertionError("non doveva connettersi")))
        self.assertEqual(chiamato, [])

    def test_401_e_un_guasto_assorbito_come_gli_altri(self):
        """Un token scaduto o rifiutato non deve far uscire il ciclo con
        un'eccezione: e' un guasto come un altro, si riprova."""
        stop = threading.Event()

        def opener(richiesta, timeout):
            return FakeRisposta(401, b"")

        def wait(secondi):
            stop.set()

        relay_client.esegui(relay_client.TunnelConfig("https://relay.test", TOKEN),
                            "grafo", "run1", lambda e: None, stop,
                            opener=opener, rand=lambda: 0.0, wait=wait)
        # non solleva: la sola prova richiesta e' che il test arrivi fin qui.

    def test_evento_che_solleva_non_abbatte_il_tunnel(self):
        opener = lambda richiesta, timeout: FakeRisposta(
            200, b'data: {"a": 1}\n\ndata: {"a": 2}\n\n')
        stop = threading.Event()
        visti = []

        def on_event_conta(evento):
            visti.append(evento)
            raise RuntimeError("boom")

        relay_client.esegui(relay_client.TunnelConfig("https://relay.test", TOKEN),
                            "grafo", "run1", on_event_conta, stop,
                            opener=opener, wait=lambda s: stop.set())
        self.assertEqual(visti, [{"a": 1}, {"a": 2}])


class NonMutaLoStatoAtlas(unittest.TestCase):
    """La proprieta' che il nodo chiede esplicitamente: una disconnessione non
    deve poter inventare una chiusura o toccare il ledger. Verificato in modo
    strutturale, non solo comportamentale: il modulo non importa nulla che
    scriva graph.json o run-state.json."""

    def test_relay_client_non_importa_moduli_che_mutano_il_ledger(self):
        sorgente = Path(relay_client.__file__).read_text(encoding="utf-8")
        albero = ast.parse(sorgente)
        importati = set()
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                importati.add(nodo.module.split(".")[-1])
        vietati = {"interactions", "mutate", "editor", "run_state", "store", "model"}
        self.assertFalse(importati & vietati, importati & vietati)


class TunnelEndToEnd(unittest.TestCase):
    """Le due meta' di D03 al lavoro insieme: il client vero apre lo stream
    contro il vero server del relay (D02/D04), il relay spinge un evento con
    RegistroTunnel.push (il gancio che D06 usera' per un tap reale) e il
    client lo consegna al chiamante."""

    def setUp(self):
        self.registro = relay_tunnel.RegistroTunnel()
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0,
                                              tunnel_token=TOKEN, registro_tunnel=self.registro)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.fermo.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_evento_pushato_dal_relay_arriva_al_client(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token=TOKEN)
        ricevuti = []
        pronto = threading.Event()
        stop = threading.Event()

        def on_event(evento):
            ricevuti.append(evento)
            pronto.set()

        filo = threading.Thread(
            target=relay_client.esegui,
            args=(config, "grafo-e2e", "run-e2e", on_event, stop),
            kwargs={"opener": urllib.request.urlopen},
            daemon=True,
        )
        filo.start()
        # attende che il client abbia registrato la sua sessione prima di spingere
        for _ in range(200):
            if self.registro.push("grafo-e2e", "run-e2e", {"kind": "callback"}):
                break
            time.sleep(0.01)
        self.assertTrue(pronto.wait(5), "l'evento pushato non e' arrivato al client")
        self.assertEqual(ricevuti, [{"kind": "callback"}])
        stop.set()
        filo.join(timeout=5)

    def test_bearer_sbagliato_401_e_il_client_non_riceve_nulla(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token="sbagliato")
        stop = threading.Event()
        chiamate = []

        def wait(secondi):
            chiamate.append(secondi)
            stop.set()

        relay_client.esegui(config, "grafo", "run1", lambda e: None, stop,
                            opener=urllib.request.urlopen, wait=wait)
        self.assertEqual(len(chiamate), 1)   # un solo giro: 401 assorbito, poi stop


class TapResultEndToEnd(unittest.TestCase):
    """aggiorna_messaggio (client) contro il vero endpoint /tunnel/tap-result
    (relay, D06): stesso principio di TunnelEndToEnd, verso outbound."""

    def setUp(self):
        self.chiamate = []
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=TOKEN,
            modifica_messaggio=lambda chat_id, message_id, testo:
                self.chiamate.append((chat_id, message_id, testo)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.fermo.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_aggiorna_messaggio_raggiunge_modifica_messaggio(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token=TOKEN)
        relay_client.aggiorna_messaggio(config, 42, 7, "Fatto: Conferma.",
                                        opener=urllib.request.urlopen)
        self.assertEqual(self.chiamate, [(42, 7, "Fatto: Conferma.")])

    def test_bearer_sbagliato_non_chiama_modifica_messaggio(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token="sbagliato")
        relay_client.aggiorna_messaggio(config, 42, 7, "x", opener=urllib.request.urlopen)
        self.assertEqual(self.chiamate, [])


if __name__ == "__main__":
    unittest.main()
