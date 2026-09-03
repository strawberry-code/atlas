"""Test del lato client del tunnel D03: config da ambiente, framing SSE,
backoff con jitter, e il ciclo di riconnessione, senza rete vera (opener
sempre iniettato) tranne un giro end-to-end contro il vero relay di D02/D04.
"""
from __future__ import annotations

import ast
import io
import sys
import tempfile
import threading
import time
import json
import shutil
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

from core import relay_client, relay_identity
import atlas_relay
import pairing
import tunnel as relay_tunnel

TOKEN = "il-bearer-del-tunnel"


class ConfigurazioneDalProfilo(unittest.TestCase):
    """Il relay si configura una volta per macchina, non a ogni sessione.

    Prima la configurazione veniva solo dall'ambiente, quindi per usare il relay
    bisognava esportare due variabili prima di ogni 'atlas serve', cioe' proprio
    il gesto che il disegno vieta al primo punto.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {"ATLAS_INSTALL_HOME": str(self.tmp)}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _scrivi_profilo(self, dati):
        (self.tmp / "relay.json").write_text(json.dumps(dati), encoding="utf-8")

    def test_senza_profilo_e_senza_ambiente_non_c_e_relay(self):
        self.assertIsNone(relay_client.configurazione(self.env))

    def test_il_profilo_basta_da_solo(self):
        self._scrivi_profilo({"url": "http://10.66.66.1:8765", "token": "segreto"})
        config = relay_client.configurazione(self.env)
        self.assertEqual("http://10.66.66.1:8765", config.base_url)
        self.assertEqual("segreto", config.token)

    def test_l_ambiente_scavalca_il_profilo(self):
        self._scrivi_profilo({"url": "http://vecchio", "token": "vecchio"})
        env = dict(self.env, RELAY_PUBLIC_URL="http://nuovo", ATLAS_RELAY_TOKEN_REF="nuovo")
        config = relay_client.configurazione(env)
        self.assertEqual("http://nuovo", config.base_url)
        self.assertEqual("nuovo", config.token)

    def test_un_profilo_rotto_non_e_un_guasto(self):
        (self.tmp / "relay.json").write_text("{ questo non e' json", encoding="utf-8")
        self.assertIsNone(relay_client.configurazione(self.env))

    def test_un_profilo_a_meta_non_vale(self):
        self._scrivi_profilo({"url": "http://10.66.66.1:8765"})
        self.assertIsNone(relay_client.configurazione(self.env))

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

    def test_url_tunnel_porta_identita_di_installazione_in_query(self):
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)
        url = config.url_tunnel("mia-installazione")
        self.assertIn("installation=mia-installazione", url)
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
    status = 200

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


class InviaMessaggio(unittest.TestCase):
    """POST '<base>/tunnel/deliver' (D07): il deliver iniziale con i
    bottoni. A differenza di aggiorna_messaggio (D06) qui il guasto NON deve
    essere assorbito: la consegna non e' ancora avvenuta."""

    def test_posta_bearer_e_corpo_corretti(self):
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)
        richieste = []

        def opener(richiesta, timeout=None):
            richieste.append(richiesta)
            return _RispostaVuota()

        relay_client.invia_messaggio(config, "la-macchina", "Serve una decisione",
                                     [("Conferma", "tok-1"), ("Rifiuta", "tok-2")], opener=opener)
        self.assertEqual(len(richieste), 1)
        richiesta = richieste[0]
        self.assertEqual(richiesta.full_url, "https://relay.test/tunnel/deliver")
        self.assertEqual(richiesta.get_header("Authorization"), f"Bearer {TOKEN}")
        import json as _json
        self.assertEqual(_json.loads(richiesta.data), {
            "installation": "la-macchina", "text": "Serve una decisione",
            "buttons": [{"label": "Conferma", "data": "tok-1"}, {"label": "Rifiuta", "data": "tok-2"}],
        })

    def test_relay_irraggiungibile_solleva(self):
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)

        def opener(richiesta, timeout=None):
            raise OSError("rete giu'")

        with self.assertRaises(OSError):
            relay_client.invia_messaggio(config, "g", "x", [], opener=opener)


class InviaFile(unittest.TestCase):
    """POST '<base>/tunnel/deliver-file' (D02): la risposta di '/view', un
    file binario in base64 dentro lo stesso JSON di ogni altra richiesta.
    Stesso principio non-assorbente di InviaMessaggio."""

    def test_posta_bearer_e_corpo_corretti(self):
        import base64
        import json as _json
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)
        richieste = []

        def opener(richiesta, timeout=None):
            richieste.append(richiesta)
            return _RispostaVuota()

        relay_client.invia_file(config, "la-macchina", "dashboard.png", b"\x89PNG",
                                "image/png", "photo", opener=opener)
        self.assertEqual(len(richieste), 1)
        richiesta = richieste[0]
        self.assertEqual(richiesta.full_url, "https://relay.test/tunnel/deliver-file")
        self.assertEqual(richiesta.get_header("Authorization"), f"Bearer {TOKEN}")
        corpo = _json.loads(richiesta.data)
        self.assertEqual(corpo["installation"], "la-macchina")
        self.assertEqual(corpo["filename"], "dashboard.png")
        self.assertEqual(corpo["mime"], "image/png")
        self.assertEqual(corpo["kind"], "photo")
        self.assertEqual(base64.b64decode(corpo["content"]), b"\x89PNG")

    def test_relay_irraggiungibile_solleva(self):
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)

        def opener(richiesta, timeout=None):
            raise OSError("rete giu'")

        with self.assertRaises(OSError):
            relay_client.invia_file(config, "g", "x", b"y", "text/html", "document", opener=opener)


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
        relay_client.esegui(config, "installazione", on_event, stop,
                            opener=opener, rand=lambda: 0.0, wait=wait)

        self.assertEqual(ricevuti, [{"tap": True}])
        self.assertEqual(len(tentativi), 2)
        self.assertEqual(len(attese), 1)

    def test_connessione_porta_la_versione_di_protocollo_dichiarata(self):
        """E02: il relay avvisa sul telefono prima di smettere di servire una
        versione vecchia, ma solo se la versione arriva. Riuso della coppia
        header/costante gia' definita da A01 (relay_identity), non una
        seconda fonte di verita'."""
        tentativi = []

        def opener(richiesta, timeout):
            tentativi.append(richiesta)
            return FakeRisposta(200, b"")

        stop = threading.Event()
        config = relay_client.TunnelConfig(base_url="https://relay.test", token=TOKEN)
        relay_client.esegui(config, "installazione", lambda evento: None, stop,
                            opener=opener, rand=lambda: 0.0, wait=lambda s: stop.set())

        self.assertEqual(len(tentativi), 1)
        # Request.get_header non normalizza in lettura (solo add_header lo fa
        # in scrittura, con .capitalize()): si legge con la stessa forma.
        self.assertEqual(
            tentativi[0].get_header(relay_identity.INTESTAZIONE_PROTOCOLLO.capitalize()),
            str(relay_identity.PROTOCOLLO))

    def test_stop_gia_segnalato_non_apre_nessuna_connessione(self):
        stop = threading.Event()
        stop.set()
        chiamato = []
        relay_client.esegui(relay_client.TunnelConfig("https://relay.test", TOKEN),
                            "installazione", chiamato.append, stop,
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
                            "installazione", lambda e: None, stop,
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
                            "installazione", on_event_conta, stop,
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
            args=(config, "installazione-e2e", on_event, stop),
            kwargs={"opener": urllib.request.urlopen},
            daemon=True,
        )
        filo.start()
        # attende che il client abbia registrato la sua linea prima di spingere
        for _ in range(200):
            if self.registro.push("installazione-e2e", {"kind": "callback"}):
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

        relay_client.esegui(config, "installazione", lambda e: None, stop,
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


class DeliverEndToEnd(unittest.TestCase):
    """invia_messaggio (client) contro il vero endpoint /tunnel/deliver
    (relay, D07), pairing vero incluso: stesso principio di
    TapResultEndToEnd, verso il deliver iniziale."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)
        self.chiamate = []
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=TOKEN, gestore_pairing=self.gestore_pairing,
            invia_bottoni=lambda chat_id, testo, bottoni: self.chiamate.append((chat_id, testo, bottoni)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_invia_messaggio_raggiunge_invia_bottoni_via_pairing(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token=TOKEN)
        relay_client.invia_messaggio(config, "la-macchina", "Serve una decisione",
                                     [("Conferma", "tok-1")], opener=urllib.request.urlopen)
        self.assertEqual(self.chiamate, [(42, "Serve una decisione", [("Conferma", "tok-1")])])

    def test_installazione_non_appaiata_solleva(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token=TOKEN)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            relay_client.invia_messaggio(config, "un-altra-macchina", "x", [],
                                         opener=urllib.request.urlopen)
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(self.chiamate, [])


class DeliverFileEndToEnd(unittest.TestCase):
    """invia_file (client, D02) contro il vero endpoint /tunnel/deliver-file
    (relay), pairing vero incluso: stesso principio di DeliverEndToEnd."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)
        self.chiamate = []
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=TOKEN, gestore_pairing=self.gestore_pairing,
            invia_file=lambda chat_id, filename, contenuto, mime, kind:
                self.chiamate.append((chat_id, filename, contenuto, mime, kind)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_invia_file_raggiunge_invia_file_via_pairing(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token=TOKEN)
        relay_client.invia_file(config, "la-macchina", "dashboard.html", b"<html></html>",
                                "text/html", "document", opener=urllib.request.urlopen)
        self.assertEqual(self.chiamate,
                         [(42, "dashboard.html", b"<html></html>", "text/html", "document")])

    def test_installazione_non_appaiata_solleva(self):
        config = relay_client.TunnelConfig(base_url=self.base_url, token=TOKEN)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            relay_client.invia_file(config, "un-altra-macchina", "x", b"y", "text/html",
                                    "document", opener=urllib.request.urlopen)
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(self.chiamate, [])


if __name__ == "__main__":
    unittest.main()
