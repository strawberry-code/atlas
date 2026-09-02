"""Test del relay isolato di D02: servizio, gate dei prerequisiti, health check
e rollback. Nessun host reale: subprocess e urlopen sono sempre iniettati.
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import atlas_relay
import deploy
import pairing
import telegram_webhook
import tunnel

SEGRETO_TEST = "il-segreto-del-webhook"


class ServizioRelay(unittest.TestCase):
    def setUp(self):
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0)
        import threading
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_healthz_risponde_200(self):
        with urllib.request.urlopen(f"{self.base_url}/healthz") as risposta:
            self.assertEqual(risposta.status, 200)
            self.assertEqual(risposta.read(), b"ok")

    def test_path_ignoto_risponde_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/altro")
        self.assertEqual(ctx.exception.code, 404)

    def test_webhook_telegram_404_se_gestore_non_configurato(self):
        richiesta = urllib.request.Request(f"{self.base_url}/telegram/webhook",
                                            data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 404)


class WebhookTelegramSulRelay(unittest.TestCase):
    """Integrazione HTTP dell'adapter D04 su atlas_relay.Handler: la logica di
    verifica/dedup/pairing e' gia' testata in isolamento in
    tests/test_telegram_webhook.py, qui si controlla solo la traduzione in
    status code HTTP."""

    def setUp(self):
        self.eventi = []
        self.pairing = telegram_webhook.MemoriaPairing((42,))
        gestore = telegram_webhook.GestoreWebhook(
            segreto_atteso=SEGRETO_TEST,
            pairing=self.pairing,
            sink=self.eventi.append,
            answer_callback=lambda callback_id: None,
        )
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0, gestore_webhook=gestore)
        import threading
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/telegram/webhook"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def _posta(self, corpo: bytes, segreto: str | None):
        headers = {}
        if segreto is not None:
            headers["X-Telegram-Bot-Api-Secret-Token"] = segreto
        richiesta = urllib.request.Request(self.url, data=corpo, headers=headers, method="POST")
        return urllib.request.urlopen(richiesta)

    def test_chat_associata_200_e_arriva_al_sink(self):
        update = {"update_id": 1, "message": {"message_id": 1, "chat": {"id": 42}}}
        import json
        with self._posta(json.dumps(update).encode("utf-8"), SEGRETO_TEST) as risposta:
            self.assertEqual(risposta.status, 200)
        self.assertEqual(len(self.eventi), 1)

    def test_segreto_sbagliato_401(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(b"{}", "sbagliato")
        self.assertEqual(ctx.exception.code, 401)
        self.assertEqual(self.eventi, [])

    def test_chat_non_associata_200_ma_niente_sink(self):
        import json
        update = {"update_id": 2, "message": {"message_id": 1, "chat": {"id": 999}}}
        with self._posta(json.dumps(update).encode("utf-8"), SEGRETO_TEST) as risposta:
            self.assertEqual(risposta.status, 200)  # nessuna info all'esterno su perche'
        self.assertEqual(self.eventi, [])


class TunnelSulRelay(unittest.TestCase):
    """Endpoint /tunnel (D03): auth del bearer, identita' di sessione in query,
    e la traduzione di RegistroTunnel.push in un frame SSE. La logica di
    RegistroTunnel/verifica_bearer e' gia' testata in isolamento in
    tests/test_tunnel.py; qui si controlla solo la traduzione HTTP."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.registro = tunnel.RegistroTunnel()
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0,
                                              tunnel_token=self.TOKEN, registro_tunnel=self.registro)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.fermo.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_404_se_il_tunnel_non_e_configurato(self):
        server = atlas_relay.crea_server(host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"http://{host}:{port}/tunnel?graph=g&runId=r")
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.fermo.set()
            server.shutdown()
            thread.join()
            server.server_close()

    def test_401_senza_bearer(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/tunnel?graph=g&runId=r")
        self.assertEqual(ctx.exception.code, 401)

    def test_401_con_bearer_sbagliato(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel?graph=g&runId=r",
                                            headers={"Authorization": "Bearer sbagliato"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 401)

    def test_400_senza_identita_di_sessione(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel",
                                            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 400)

    def test_stream_aperto_riceve_il_battito_iniziale(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel?graph=g&runId=r",
                                            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta, timeout=5) as risposta:
            self.assertEqual(risposta.status, 200)
            self.assertEqual(risposta.headers.get("Content-Type"), "text/event-stream")

    def test_push_arriva_come_frame_tap(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel?graph=g&runId=r",
                                            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta, timeout=5) as risposta:
            for _ in range(200):
                if self.registro.push("g", "r", {"tap": True}):
                    break
                time.sleep(0.01)
            righe = []
            while True:
                riga = risposta.readline().decode("utf-8")
                righe.append(riga)
                if riga.strip() == "" and any("data:" in r for r in righe):
                    break
            self.assertIn("event: tap\n", righe)
            self.assertTrue(any('"tap": true' in r for r in righe))

    def test_push_verso_sessione_non_connessa_si_perde(self):
        self.assertFalse(self.registro.push("nessuno", "qui", {"tap": True}))


class TapResultSulRelay(unittest.TestCase):
    """Endpoint /tunnel/tap-result (D06): il client chiede di aggiornare un
    messaggio Telegram dopo aver risolto un'Interaction. Stesso bearer del
    tunnel, 404 se il webhook non e' configurato in questo processo."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.chiamate = []
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN,
            modifica_messaggio=lambda chat_id, message_id, testo:
                self.chiamate.append((chat_id, message_id, testo)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/tunnel/tap-result"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def _posta(self, corpo: dict, token: str | None = TOKEN):
        import json
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        richiesta = urllib.request.Request(self.url, data=json.dumps(corpo).encode("utf-8"),
                                           headers=headers, method="POST")
        return urllib.request.urlopen(richiesta)

    def test_200_e_chiama_modifica_messaggio(self):
        with self._posta({"chatId": 42, "messageId": 7, "text": "Fatto."}) as risposta:
            self.assertEqual(risposta.status, 200)
        self.assertEqual(self.chiamate, [(42, 7, "Fatto.")])

    def test_401_senza_bearer(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta({"chatId": 42, "messageId": 7, "text": "x"}, token=None)
        self.assertEqual(ctx.exception.code, 401)
        self.assertEqual(self.chiamate, [])

    def test_400_con_corpo_incompleto(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta({"chatId": 42})
        self.assertEqual(ctx.exception.code, 400)

    def test_404_se_non_configurato(self):
        server = atlas_relay.crea_server(host="127.0.0.1", port=0, tunnel_token=self.TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            richiesta = urllib.request.Request(
                f"http://{host}:{port}/tunnel/tap-result", data=b"{}",
                headers={"Authorization": f"Bearer {self.TOKEN}"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(richiesta)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


class InoltroTapEndToEnd(unittest.TestCase):
    """Le tre meta' di D06 assemblate come farebbe atlas_relay.main(): un tap
    verificato dal webhook (D04) arriva al sink costruito da
    tunnel.costruisci_instradamento (D06), che lo spinge sulla sessione
    (graph, runId) giusta del RegistroTunnel (D03) risolvendo il progetto dal
    pairing (D05)."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.registro = tunnel.RegistroTunnel()
        self.pairing = telegram_webhook.MemoriaPairing((42,))
        self.pairing.progetto_di = lambda chat_id: "il-progetto" if chat_id == 42 else None
        sink = tunnel.costruisci_instradamento(self.pairing.progetto_di, self.registro)
        gestore = telegram_webhook.GestoreWebhook(
            segreto_atteso=SEGRETO_TEST, pairing=self.pairing, sink=sink,
            answer_callback=lambda callback_id: None)
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0,
                                              gestore_webhook=gestore, tunnel_token=self.TOKEN,
                                              registro_tunnel=self.registro)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.fermo.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_tap_di_chat_associata_arriva_al_tunnel_giusto(self):
        richiesta_tunnel = urllib.request.Request(
            f"{self.base_url}/tunnel?graph=il-progetto&runId=run-1",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta_tunnel, timeout=5) as risposta:
            self.assertEqual(risposta.status, 200)
            for _ in range(200):
                if self.registro.sessioni_di("il-progetto"):
                    break
                time.sleep(0.01)

            import json
            update = {"update_id": 1, "callback_query": {
                "id": "cb-1", "data": "il-token", "message": {"message_id": 5, "chat": {"id": 42}}}}
            richiesta_webhook = urllib.request.Request(
                f"{self.base_url}/telegram/webhook", data=json.dumps(update).encode("utf-8"),
                headers={"X-Telegram-Bot-Api-Secret-Token": SEGRETO_TEST}, method="POST")
            with urllib.request.urlopen(richiesta_webhook) as esito:
                self.assertEqual(esito.status, 200)

            righe = []
            while True:
                riga = risposta.readline().decode("utf-8")
                righe.append(riga)
                if riga.strip() == "" and any("data:" in r for r in righe):
                    break
            self.assertIn("event: tap\n", righe)
            self.assertTrue(any('"callback_data": "il-token"' in r for r in righe))


class PairingSulRelay(unittest.TestCase):
    """Endpoint /pairing (D05): stesso bearer del tunnel, POST richiede un
    codice, GET ne legge lo stato. La logica di GestorePairing e' gia'
    testata in isolamento in tests/test_pairing.py; qui si controlla solo la
    traduzione HTTP."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN,
            gestore_pairing=self.gestore, pairing_bot_username="atlas_bot")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def _post(self, corpo: bytes, autorizzato: bool = True):
        headers = {"Authorization": f"Bearer {self.TOKEN}"} if autorizzato else {}
        richiesta = urllib.request.Request(f"{self.base_url}/pairing", data=corpo,
                                            headers=headers, method="POST")
        return urllib.request.urlopen(richiesta)

    def test_richiedi_torna_codice_e_link_t_me(self):
        import json
        with self._post(json.dumps({"graph": "prova"}).encode("utf-8")) as risposta:
            self.assertEqual(risposta.status, 200)
            corpo = json.loads(risposta.read())
        self.assertIn("code", corpo)
        self.assertEqual(corpo["url"], f"https://t.me/atlas_bot?start={corpo['code']}")
        self.assertIn("expiresAt", corpo)

    def test_richiedi_senza_bearer_401(self):
        import json
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(json.dumps({"graph": "prova"}).encode("utf-8"), autorizzato=False)
        self.assertEqual(ctx.exception.code, 401)

    def test_richiedi_senza_graph_400(self):
        import json
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(json.dumps({}).encode("utf-8"))
        self.assertEqual(ctx.exception.code, 400)

    def test_404_se_pairing_non_configurato(self):
        import json
        server = atlas_relay.crea_server(host="127.0.0.1", port=0, tunnel_token=self.TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            richiesta = urllib.request.Request(
                f"http://{host}:{port}/pairing", data=json.dumps({"graph": "prova"}).encode("utf-8"),
                headers={"Authorization": f"Bearer {self.TOKEN}"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(richiesta)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_stato_in_attesa_poi_associato(self):
        import json
        with self._post(json.dumps({"graph": "prova"}).encode("utf-8")) as risposta:
            codice = json.loads(risposta.read())["code"]

        richiesta = urllib.request.Request(
            f"{self.base_url}/pairing?code={codice}", headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta) as risposta:
            self.assertEqual(json.loads(risposta.read()), {"status": "in_attesa"})

        self.gestore.conferma(codice, 42)
        with urllib.request.urlopen(richiesta) as risposta:
            self.assertEqual(json.loads(risposta.read()), {"status": "associato"})

    def test_stato_senza_bearer_401(self):
        richiesta = urllib.request.Request(f"{self.base_url}/pairing?code=x")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 401)

    def test_stato_senza_code_400(self):
        richiesta = urllib.request.Request(f"{self.base_url}/pairing",
                                            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 400)


class PrerequisitiDeploy(unittest.TestCase):
    ENV_COMPLETO = {
        "RELAY_HTTPS_HOSTNAME": "relay.esempio.test",
        "ATLAS_RELAY_TOKEN_REF": "op://vault/atlas-relay-token",
        "ATLAS_RELAY_DEPLOY_HOST": "utente@host.esempio.test",
        "ATLAS_RELAY_DEPLOY_PATH": "/opt/atlas-relay",
    }

    def test_rifiuta_se_mancano_prerequisiti(self):
        with self.assertRaises(deploy.PrerequisitiMancanti) as ctx:
            deploy.verifica_prerequisiti({})
        for nome in deploy.PREREQUISITI:
            self.assertIn(nome, str(ctx.exception))

    def test_passa_con_ambiente_completo(self):
        deploy.verifica_prerequisiti(self.ENV_COMPLETO)  # non solleva


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class FakeRunner:
    def __init__(self, readlink_stdout="/opt/atlas-relay/releases/0.0.0"):
        self.chiamate = []
        self.readlink_stdout = readlink_stdout

    def __call__(self, argv, **kwargs):
        self.chiamate.append(argv)
        if "readlink" in argv:
            return FakeCompletedProcess(0, self.readlink_stdout)
        return FakeCompletedProcess(0)


class FakeRisposta:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class HealthCheck(unittest.TestCase):
    ENV = PrerequisitiDeploy.ENV_COMPLETO

    def test_successo_al_primo_tentativo(self):
        opener = lambda url, timeout: FakeRisposta(200)
        self.assertTrue(deploy.controlla_salute(self.ENV, tentativi=3, opener=opener, sleep=lambda s: None))

    def test_fallisce_dopo_n_tentativi(self):
        def opener(url, timeout):
            raise urllib.error.URLError("connessione rifiutata")

        attese = []
        ok = deploy.controlla_salute(self.ENV, tentativi=3, attesa=0.01, opener=opener,
                                      sleep=attese.append)
        self.assertFalse(ok)
        self.assertEqual(len(attese), 2)  # nessuna attesa dopo l'ultimo tentativo


class DeployRollback(unittest.TestCase):
    ENV = PrerequisitiDeploy.ENV_COMPLETO

    def test_health_ok_non_fa_rollback(self):
        runner = FakeRunner()
        opener = lambda url, timeout: FakeRisposta(200)
        deploy.deploy(self.ENV, "1.2.3", runner=runner, opener=opener, sleep=lambda s: None)
        comandi = [" ".join(c) for c in runner.chiamate]
        self.assertTrue(any("restart" in c for c in comandi))
        self.assertEqual(sum("ln" in c for c in comandi), 1)  # solo lo switch iniziale, nessun rollback

    def test_health_fallito_fa_rollback_e_solleva(self):
        runner = FakeRunner(readlink_stdout="/opt/atlas-relay/releases/0.0.0")

        def opener(url, timeout):
            raise urllib.error.URLError("giu'")

        with self.assertRaises(RuntimeError) as ctx:
            deploy.deploy(self.ENV, "1.2.3", runner=runner, opener=opener, sleep=lambda s: None)
        self.assertIn("rollback", str(ctx.exception))
        comandi = [" ".join(c) for c in runner.chiamate]
        self.assertEqual(sum("ln" in c for c in comandi), 2)  # switch al nuovo + rollback al precedente
        self.assertEqual(sum("restart" in c for c in comandi), 2)  # restart dopo il deploy + dopo il rollback

    def test_health_fallito_senza_precedente_solleva_senza_rollback(self):
        runner = FakeRunner(readlink_stdout="")

        def opener(url, timeout):
            raise urllib.error.URLError("giu'")

        with self.assertRaises(RuntimeError) as ctx:
            deploy.deploy(self.ENV, "1.2.3", runner=runner, opener=opener, sleep=lambda s: None)
        self.assertIn("nessun rilascio precedente", str(ctx.exception))

    def test_rifiuta_prima_di_toccare_qualunque_comando_se_mancano_prerequisiti(self):
        runner = FakeRunner()
        with self.assertRaises(deploy.PrerequisitiMancanti):
            deploy.deploy({}, "1.2.3", runner=runner)
        self.assertEqual(runner.chiamate, [])


if __name__ == "__main__":
    unittest.main()
