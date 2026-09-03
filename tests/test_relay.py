"""Test del relay isolato di D02: servizio, gate dei prerequisiti, health check
e rollback. Nessun host reale: subprocess e urlopen sono sempre iniettati.
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import atlas_relay
import capability_store
import deploy
import devices
import pairing
import peers
import protocol_watch
import status_commands
import telegram_webhook
import throttle
import tunnel
import view_command


class IndirizzoDelControlloSalute(unittest.TestCase):
    """L'health check bussa dove il servizio ascolta, non dove ascoltava prima.

    Regressione del 2026-09-03: il controllo era inchiodato su 127.0.0.1, ma il
    bind e' una scelta dell'installazione. Con un relay in ascolto sull'indirizzo
    di una VPN ogni deploy finiva in rollback su un rilascio sano, e nessun
    messaggio nominava la causa.
    """

    def test_il_default_resta_il_loopback(self):
        self.assertEqual("http://127.0.0.1:8765/healthz", deploy.url_di_salute({}))

    def test_host_e_porta_dichiarati_vincono(self):
        env = {"ATLAS_RELAY_HOST": "10.66.66.1", "ATLAS_RELAY_PORT": "9000"}
        self.assertEqual("http://10.66.66.1:9000/healthz", deploy.url_di_salute(env))

    def test_il_controllo_interroga_quell_indirizzo(self):
        comandi = []

        def runner(argv, **kwargs):
            comandi.append(argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        deploy.controlla_salute(
            {"ATLAS_RELAY_DEPLOY_HOST": "utente@host", "ATLAS_RELAY_HOST": "10.66.66.1"},
            runner=runner, sleep=lambda _s: None)

        self.assertIn("http://10.66.66.1:8765/healthz", comandi[0])


class SuperficiePubblica(unittest.TestCase):
    """Cio' che il servizio serve e cio' che il proxy espone devono coincidere.

    Sono due file che nessuno rilegge insieme: il primo cresce quando si aggiunge
    un endpoint, il secondo solo se qualcuno se ne ricorda. Se il proxy resta
    indietro l'endpoint nuovo non risponde ai client, se va avanti espone su
    Internet un path che il servizio non ha piu'.
    """

    RELAY = Path(__file__).resolve().parent.parent / "relay"

    def _path_del_servizio(self) -> set[str]:
        import re
        sorgente = (self.RELAY / "atlas_relay.py").read_text(encoding="utf-8")
        # '/healthz' e' scritto in chiaro nel dispatch, gli altri sono costanti
        return set(re.findall(r'^[A-Z_]+_PATH = "([^"]+)"', sorgente, re.M)) | {"/healthz"}

    def _path_del_proxy(self) -> set[str]:
        import re
        caddyfile = (self.RELAY / "Caddyfile.atlas-relay").read_text(encoding="utf-8")
        riga = re.search(r"@relay path (.+)", caddyfile)
        self.assertIsNotNone(riga, "il Caddyfile non elenca piu' i path ammessi")
        return set(riga.group(1).split())

    def test_il_proxy_espone_esattamente_i_path_del_servizio(self):
        self.assertEqual(self._path_del_servizio(), self._path_del_proxy())


class ModuliDelRollout(unittest.TestCase):
    """Sul remote deve arrivare ogni modulo del relay, senza elenchi da ricordare.

    L'elenco scritto a mano ha dimenticato un modulo quattro volte, e il guasto e'
    sempre lo stesso: il servizio non parte perche' un import fallisce prima di
    main(), cioe' si scopre dopo il deploy invece che qui.
    """

    RELAY = Path(__file__).resolve().parent.parent / "relay"

    def test_il_rollout_copia_ogni_modulo_tranne_l_orchestratore(self):
        comandi = []
        env = {"ATLAS_RELAY_TOKEN_REF": "x", "ATLAS_RELAY_DEPLOY_HOST": "utente@host",
               "ATLAS_RELAY_DEPLOY_PATH": "/opt/atlas-relay"}
        def runner(argv, **kwargs):
            comandi.append(argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        deploy.rilascia(env, "1.0.0", runner=runner)

        rsync = [argv for argv in comandi if argv[0] == "rsync"][0]
        copiati = {Path(arg).name for arg in rsync if arg.endswith(".py")}
        attesi = {percorso.name for percorso in self.RELAY.glob("*.py")} - {"deploy.py"}

        self.assertEqual(attesi, copiati)
        self.assertNotIn("deploy.py", copiati)


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

    def test_webhook_telegram_smontato_risponde_404(self):
        """G02: l'endpoint non esiste piu', qualunque path/verbo ci finisca
        sopra si comporta come un path ignoto qualunque."""
        richiesta = urllib.request.Request(f"{self.base_url}/telegram/webhook",
                                            data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 404)


class TunnelSulRelay(unittest.TestCase):
    """Endpoint /tunnel (D03): auth del bearer, identita' di installazione in
    query (A05), e la traduzione di RegistroTunnel.push in un frame SSE. La
    logica di RegistroTunnel/verifica_bearer e' gia' testata in isolamento in
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
                urllib.request.urlopen(f"http://{host}:{port}/tunnel?installation=inst")
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.fermo.set()
            server.shutdown()
            thread.join()
            server.server_close()

    def test_401_senza_bearer(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/tunnel?installation=inst")
        self.assertEqual(ctx.exception.code, 401)

    def test_401_con_bearer_sbagliato(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel?installation=inst",
                                            headers={"Authorization": "Bearer sbagliato"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 401)

    def test_400_senza_identita_di_installazione(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel",
                                            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 400)

    def test_stream_aperto_riceve_il_battito_iniziale(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel?installation=inst",
                                            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta, timeout=5) as risposta:
            self.assertEqual(risposta.status, 200)
            self.assertEqual(risposta.headers.get("Content-Type"), "text/event-stream")

    def test_push_arriva_come_frame_tap(self):
        richiesta = urllib.request.Request(f"{self.base_url}/tunnel?installation=inst",
                                            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta, timeout=5) as risposta:
            for _ in range(200):
                if self.registro.push("inst", {"tap": True}):
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

    def test_push_verso_installazione_non_connessa_si_perde(self):
        self.assertFalse(self.registro.push("nessuno", {"tap": True}))


class SegnaVistaAllaConnessioneDelTunnel(unittest.TestCase):
    """Il segnale di attivita' di C02 (S7-ter/5): aprire una linea sul
    tunnel aggiorna 'ultima vista' dell'installazione nel pairing, senza
    bisogno di un battito dedicato."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)
        self.registro = tunnel.RegistroTunnel()
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN,
            registro_tunnel=self.registro, gestore_pairing=self.gestore_pairing)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.fermo.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_connessione_aggiorna_ultima_vista(self):
        prima = self.gestore_pairing.ultima_vista("la-macchina")
        richiesta = urllib.request.Request(
            f"{self.base_url}/tunnel?installation=la-macchina",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta, timeout=5):
            dopo = self.gestore_pairing.ultima_vista("la-macchina")
        self.assertGreaterEqual(dopo, prima)

    def test_connessione_di_installazione_non_appaiata_non_solleva(self):
        richiesta = urllib.request.Request(
            f"{self.base_url}/tunnel?installation=mai-vista",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta, timeout=5) as risposta:
            self.assertEqual(risposta.status, 200)
        self.assertIsNone(self.gestore_pairing.ultima_vista("mai-vista"))


class AvvisoProtocolloAllaConnessioneDelTunnel(unittest.TestCase):
    """L'avviso di fine servizio (E02, S7-ter/6): la connessione del tunnel
    porta la versione dichiarata in 'X-Atlas-Protocol' (A01), e sotto soglia
    scatta l'avviso su Telegram, allo stesso punto di segna_vista sopra."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)
        self.messaggi = []
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        avvisa = protocol_watch.costruisci_avviso(
            avviso, self.gestore_pairing, lambda chat_id, testo: self.messaggi.append((chat_id, testo)))
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN,
            registro_tunnel=tunnel.RegistroTunnel(), gestore_pairing=self.gestore_pairing,
            avvisa_protocollo=avvisa)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.fermo.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_versione_sotto_soglia_manda_l_avviso(self):
        richiesta = urllib.request.Request(
            f"{self.base_url}/tunnel?installation=la-macchina",
            headers={"Authorization": f"Bearer {self.TOKEN}",
                     protocol_watch.INTESTAZIONE_PROTOCOLLO: "1"})
        with urllib.request.urlopen(richiesta, timeout=5):
            # la connessione torna al client appena il relay manda gli header
            # HTTP, prima che il thread del server esegua avvisa_protocollo:
            # stesso poll di test_push_arriva_come_frame_tap sopra.
            for _ in range(200):
                if self.messaggi:
                    break
                time.sleep(0.01)
        self.assertEqual(self.messaggi, [(42, protocol_watch.MESSAGGIO)])

    def test_senza_header_di_protocollo_non_avvisa(self):
        richiesta = urllib.request.Request(
            f"{self.base_url}/tunnel?installation=la-macchina",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta, timeout=5):
            time.sleep(0.2)   # tempo piu' che sufficiente perche' l'avviso, se ci fosse, sia gia' partito
        self.assertEqual(self.messaggi, [])

    def test_senza_avvisa_protocollo_configurato_non_solleva(self):
        server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN,
            registro_tunnel=tunnel.RegistroTunnel())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            richiesta = urllib.request.Request(
                f"http://{host}:{port}/tunnel?installation=la-macchina",
                headers={"Authorization": f"Bearer {self.TOKEN}",
                         protocol_watch.INTESTAZIONE_PROTOCOLLO: "1"})
            with urllib.request.urlopen(richiesta, timeout=5) as risposta:
                self.assertEqual(risposta.status, 200)
        finally:
            server.fermo.set()
            server.shutdown()
            thread.join()
            server.server_close()


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


class DeliverSulRelay(unittest.TestCase):
    """Endpoint /tunnel/deliver (D07): il client chiede il deliver iniziale
    di un'Interazione con i suoi bottoni. Stesso bearer del tunnel, il chat_id
    si risolve dall'installazione via il pairing vero (D05/A02), 409 se non
    appaiata, 404 se Telegram non e' configurato in questo processo, 502 se
    Telegram rifiuta l'invio."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)
        self.chiamate = []
        self.store = capability_store.StoreCapability()
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN, gestore_pairing=self.gestore_pairing,
            invia_bottoni=lambda chat_id, testo, bottoni: self.chiamate.append((chat_id, testo, bottoni)),
            capability_store=self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/tunnel/deliver"

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

    def _corpo(self, **over):
        base = {"installation": "la-macchina", "text": "Serve una decisione",
                "buttons": [{"label": "Conferma", "data": "tok-1"}]}
        base.update(over)
        return base

    def test_200_risolve_il_chat_id_e_chiama_invia_bottoni(self):
        with self._posta(self._corpo()) as risposta:
            self.assertEqual(risposta.status, 200)
        self.assertEqual(len(self.chiamate), 1)
        chat_id, testo, bottoni = self.chiamate[0]
        self.assertEqual((chat_id, testo), (42, "Serve una decisione"))
        # D08: 'invia_bottoni' non vede piu' il capability token ('tok-1')
        # ma l'identificativo corto emesso dallo store, risolvibile a ritroso.
        self.assertEqual([etichetta for etichetta, _ in bottoni], ["Conferma"])
        identificativo = bottoni[0][1]
        self.assertNotEqual(identificativo, "tok-1")
        self.assertLessEqual(len(identificativo.encode("utf-8")), 64)
        self.assertEqual(self.store.preleva(identificativo), "tok-1")

    def test_401_senza_bearer(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo(), token=None)
        self.assertEqual(ctx.exception.code, 401)
        self.assertEqual(self.chiamate, [])

    def test_400_con_corpo_incompleto(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta({"installation": "la-macchina"})
        self.assertEqual(ctx.exception.code, 400)

    def test_409_se_l_installazione_non_e_appaiata(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo(installation="un-altra-macchina"))
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(self.chiamate, [])

    def test_502_se_telegram_rifiuta_l_invio(self):
        def invia_bottoni_rotto(chat_id, testo, bottoni):
            raise urllib.error.URLError("giu'")

        self.server.invia_bottoni = invia_bottoni_rotto
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo())
        self.assertEqual(ctx.exception.code, 502)

    def test_404_se_non_configurato(self):
        server = atlas_relay.crea_server(host="127.0.0.1", port=0, tunnel_token=self.TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            richiesta = urllib.request.Request(
                f"http://{host}:{port}/tunnel/deliver", data=b"{}",
                headers={"Authorization": f"Bearer {self.TOKEN}"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(richiesta)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


class PeersNotifySulRelay(unittest.TestCase):
    """Endpoint /peers/notify (E01): un'installazione avvisa che ha chiuso un
    pezzo di un progetto condiviso, il relay registra chi ha avvisato e
    spinge il testo muto ai pari gia' noti per lo stesso codice opaco.
    Stesso bearer del tunnel, stesso 404 se il pairing non e' configurato."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        for installation_id, chat_id in (("mac-a", 42), ("mac-b", 43)):
            codice, _ = self.gestore_pairing.richiedi(installation_id)
            self.gestore_pairing.richiedi_ingresso(codice, chat_id, "tester")
            self.gestore_pairing.approva(codice)
        self.messaggi = []
        registro_peer = peers.RegistroPeer(Path(self.tmp.name) / "peers.json")
        avviso_peer = peers.costruisci_avviso(
            registro_peer, self.gestore_pairing.chat_id_di,
            lambda chat_id, testo: self.messaggi.append((chat_id, testo)))
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN, gestore_pairing=self.gestore_pairing,
            avviso_peer=avviso_peer)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/peers/notify"

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

    def test_primo_ad_avvisare_non_sveglia_nessuno(self):
        with self._posta({"projectCode": "codice-1", "installation": "mac-a"}) as risposta:
            self.assertEqual(risposta.status, 200)
        self.assertEqual(self.messaggi, [])

    def test_secondo_ad_avvisare_sveglia_il_primo(self):
        self._posta({"projectCode": "codice-1", "installation": "mac-a"})
        with self._posta({"projectCode": "codice-1", "installation": "mac-b"}) as risposta:
            self.assertEqual(risposta.status, 200)
        self.assertEqual(self.messaggi, [(42, peers.TESTO_AVVISO)])

    def test_codici_diversi_non_si_avvisano_a_vicenda(self):
        self._posta({"projectCode": "codice-1", "installation": "mac-a"})
        self._posta({"projectCode": "codice-2", "installation": "mac-b"})
        self.assertEqual(self.messaggi, [])

    def test_401_senza_bearer(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta({"projectCode": "codice-1", "installation": "mac-a"}, token=None)
        self.assertEqual(ctx.exception.code, 401)

    def test_400_con_corpo_incompleto(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta({"projectCode": "codice-1"})
        self.assertEqual(ctx.exception.code, 400)

    def test_404_se_non_configurato(self):
        server = atlas_relay.crea_server(host="127.0.0.1", port=0, tunnel_token=self.TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            richiesta = urllib.request.Request(
                f"http://{host}:{port}/peers/notify", data=b"{}",
                headers={"Authorization": f"Bearer {self.TOKEN}"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(richiesta)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


class DeliverFileSulRelay(unittest.TestCase):
    """Endpoint /tunnel/deliver-file (D02): come /tunnel/deliver ma per la
    risposta di '/view', un file binario in base64 invece di testo e
    bottoni. Stesso bearer, stesso 409/404/429, 502 se Telegram rifiuta."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)
        self.chiamate = []
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN, gestore_pairing=self.gestore_pairing,
            invia_file=lambda chat_id, filename, contenuto, mime, kind:
                self.chiamate.append((chat_id, filename, contenuto, mime, kind)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/tunnel/deliver-file"

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

    def _corpo(self, **over):
        import base64
        base = {"installation": "la-macchina", "filename": "dashboard.png", "mime": "image/png",
                "kind": "photo", "content": base64.b64encode(b"\x89PNG").decode("ascii")}
        base.update(over)
        return base

    def test_200_risolve_il_chat_id_e_chiama_invia_file(self):
        with self._posta(self._corpo()) as risposta:
            self.assertEqual(risposta.status, 200)
        self.assertEqual(len(self.chiamate), 1)
        chat_id, filename, contenuto, mime, kind = self.chiamate[0]
        self.assertEqual((chat_id, filename, mime, kind), (42, "dashboard.png", "image/png", "photo"))
        self.assertEqual(contenuto, b"\x89PNG")

    def test_401_senza_bearer(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo(), token=None)
        self.assertEqual(ctx.exception.code, 401)
        self.assertEqual(self.chiamate, [])

    def test_400_con_corpo_incompleto(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta({"installation": "la-macchina"})
        self.assertEqual(ctx.exception.code, 400)

    def test_400_con_kind_sconosciuto(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo(kind="messaggio"))
        self.assertEqual(ctx.exception.code, 400)

    def test_400_con_content_non_base64(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo(content="non e' base64 valido!!"))
        self.assertEqual(ctx.exception.code, 400)

    def test_409_se_l_installazione_non_e_appaiata(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo(installation="un-altra-macchina"))
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(self.chiamate, [])

    def test_502_se_telegram_rifiuta_l_invio(self):
        def invia_file_rotto(chat_id, filename, contenuto, mime, kind):
            raise urllib.error.URLError("giu'")

        self.server.invia_file = invia_file_rotto
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta(self._corpo())
        self.assertEqual(ctx.exception.code, 502)

    def test_404_se_non_configurato(self):
        server = atlas_relay.crea_server(host="127.0.0.1", port=0, tunnel_token=self.TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            richiesta = urllib.request.Request(
                f"http://{host}:{port}/tunnel/deliver-file", data=b"{}",
                headers={"Authorization": f"Bearer {self.TOKEN}"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(richiesta)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


class FrenoSulRelay(unittest.TestCase):
    """Il freno automatico (C01) applicato all'endpoint /tunnel/deliver: oltre
    la soglia il relay risponde 429 invece di chiamare Telegram, e avvisa la
    macchina fermata alla prima volta che la supera."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)
        self.chiamate = []
        self.avvisi = []
        self.freno = throttle.FrenoOrario(soglia=2)
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, tunnel_token=self.TOKEN, gestore_pairing=self.gestore_pairing,
            invia_bottoni=lambda chat_id, testo, bottoni: self.chiamate.append((chat_id, testo, bottoni)),
            capability_store=capability_store.StoreCapability(),
            freno_orario=self.freno,
            notifica_blocco_freno=lambda installation_id, chat_id: self.avvisi.append(
                (installation_id, chat_id)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/tunnel/deliver"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def _posta(self):
        import json
        corpo = {"installation": "la-macchina", "text": "Serve una decisione",
                 "buttons": [{"label": "Conferma", "data": "tok-1"}]}
        richiesta = urllib.request.Request(
            self.url, data=json.dumps(corpo).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.TOKEN}", "Content-Type": "application/json"},
            method="POST")
        return urllib.request.urlopen(richiesta)

    def test_sotto_soglia_passa(self):
        for _ in range(2):
            with self._posta() as risposta:
                self.assertEqual(risposta.status, 200)
        self.assertEqual(len(self.chiamate), 2)
        self.assertEqual(self.avvisi, [])

    def test_oltre_soglia_429_e_avvisa_una_volta_sola(self):
        for _ in range(2):
            with self._posta():
                pass
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta()
        self.assertEqual(ctx.exception.code, 429)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._posta()
        self.assertEqual(ctx.exception.code, 429)
        self.assertEqual(len(self.chiamate), 2)   # i tentativi respinti non chiamano Telegram
        self.assertEqual(self.avvisi, [("la-macchina", 42)])   # un solo avviso, non uno per tentativo


class DispositiviEndToEnd(unittest.TestCase):
    """'/computer' e il tap 'Stacca' (C02) assemblati come farebbe
    atlas_relay.main(): il traduttore (D04, G02: alimentato dal polling, non
    piu' da un webhook HTTP) instrada entrambi al confine costruito da
    devices.py, prima del cancello 'is_paired' per il comando e attraverso
    lo stesso 'admin_decision' gia' condiviso da pairing e freno per il tap."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)

        self.messaggi = []
        self.bottoni = []
        self.modifiche = []
        comando = devices.costruisci_comando(
            self.gestore_pairing, lambda c, t: self.messaggi.append((c, t)),
            lambda c, t, b: self.bottoni.append((c, t, b)))
        decisione = devices.costruisci_decision(
            self.gestore_pairing, lambda c, t: self.messaggi.append((c, t)),
            lambda c, m, t: self.modifiche.append((c, m, t)))
        self.gestore_webhook = telegram_webhook.GestoreWebhook(
            pairing=self.gestore_pairing, sink=lambda evento: None,
            answer_callback=lambda callback_id: None,
            dispositivi_comando=comando, admin_decision=decisione)

    def test_computer_elenca_e_poi_stacca_dimentica_linstallazione(self):
        self.gestore_webhook.processa_update({"update_id": 1, "message": {
                "message_id": 1, "chat": {"id": 42}, "text": "/computer"}})
        self.assertEqual(len(self.bottoni), 1)
        _, _, tasti = self.bottoni[0]
        etichetta, dato = tasti[0]
        self.assertEqual(dato, f"{devices.PREFISSO_STACCA}la-macchina")

        self.gestore_webhook.processa_update({"update_id": 2, "callback_query": {
                "id": "cb-1", "data": dato,
                "message": {"message_id": 9, "chat": {"id": 42}}}})

        self.assertEqual(self.modifiche, [(42, 9, "Staccato: la-macchina.")])
        self.assertFalse(self.gestore_pairing.is_paired(42))


class ComandiStatoEndToEnd(unittest.TestCase):
    """I tre comandi di stato (D01) assemblati come farebbe atlas_relay.main():
    il traduttore (D04, G02: alimentato dal polling) li ferma dopo il
    cancello 'is_paired' e li passa al confine costruito da
    status_commands.py, che spinge sulla linea del tunnel gia' aperta
    (D03/A05) o, se non c'e' nessuna linea, risponde subito che il computer
    non e' in linea (S7-ter/2)."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.registro = tunnel.RegistroTunnel()
        self.pairing = telegram_webhook.MemoriaPairing((42,))
        self.messaggi = []
        risolvi = lambda chat_id: "l-installazione" if chat_id == 42 else None
        comando_stato = status_commands.costruisci_comando_stato(
            risolvi, self.registro.push, lambda c, t: self.messaggi.append((c, t)))
        self.gestore = telegram_webhook.GestoreWebhook(
            pairing=self.pairing, sink=lambda evento: None,
            answer_callback=lambda callback_id: None, comando_stato=comando_stato)
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0,
                                              gestore_webhook=self.gestore, tunnel_token=self.TOKEN,
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

    def _manda_comando(self, testo: str):
        self.gestore.processa_update({"update_id": 1, "message": {
            "message_id": 3, "chat": {"id": 42}, "text": testo}})

    def test_con_la_linea_aperta_il_comando_arriva_al_tunnel_e_non_manda_offline(self):
        richiesta_tunnel = urllib.request.Request(
            f"{self.base_url}/tunnel?installation=l-installazione",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta_tunnel, timeout=5) as risposta:
            self.assertEqual(risposta.status, 200)
            self._manda_comando("/stato")

            righe = []
            while True:
                riga = risposta.readline().decode("utf-8")
                righe.append(riga)
                if riga.strip() == "" and any("data:" in r for r in righe):
                    break
            self.assertTrue(any('"text": "/stato"' in r for r in righe))
        self.assertEqual(self.messaggi, [])

    def test_senza_nessuna_linea_aperta_risponde_subito_non_in_linea(self):
        self._manda_comando("/aspetta")
        self.assertEqual(self.messaggi, [(42, status_commands.OFFLINE)])


class ViewEndToEnd(unittest.TestCase):
    """'/view' (D02) assemblato come farebbe atlas_relay.main(): stesso
    principio di ComandiStatoEndToEnd, un confine a se' perche' la sua
    risposta e' un file, non un messaggio (comando_view, non comando_stato)."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.registro = tunnel.RegistroTunnel()
        self.pairing = telegram_webhook.MemoriaPairing((42,))
        self.messaggi = []
        risolvi = lambda chat_id: "l-installazione" if chat_id == 42 else None
        comando_view = view_command.costruisci_comando_view(
            risolvi, self.registro.push, lambda c, t: self.messaggi.append((c, t)))
        self.gestore = telegram_webhook.GestoreWebhook(
            pairing=self.pairing, sink=lambda evento: None,
            answer_callback=lambda callback_id: None, comando_view=comando_view)
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0,
                                              gestore_webhook=self.gestore, tunnel_token=self.TOKEN,
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

    def _manda_comando(self, testo: str):
        self.gestore.processa_update({"update_id": 1, "message": {
            "message_id": 3, "chat": {"id": 42}, "text": testo}})

    def test_con_la_linea_aperta_il_comando_arriva_al_tunnel_e_non_manda_offline(self):
        richiesta_tunnel = urllib.request.Request(
            f"{self.base_url}/tunnel?installation=l-installazione",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta_tunnel, timeout=5) as risposta:
            self.assertEqual(risposta.status, 200)
            self._manda_comando("/view")

            righe = []
            while True:
                riga = risposta.readline().decode("utf-8")
                righe.append(riga)
                if riga.strip() == "" and any("data:" in r for r in righe):
                    break
            self.assertTrue(any('"text": "/view"' in r for r in righe))
        self.assertEqual(self.messaggi, [])

    def test_senza_nessuna_linea_aperta_risponde_subito_non_in_linea(self):
        self._manda_comando("/view")
        self.assertEqual(self.messaggi, [(42, view_command.OFFLINE)])


class InoltroTapEndToEnd(unittest.TestCase):
    """Le tre meta' di D06 assemblate come farebbe atlas_relay.main(): un tap
    tradotto dal traduttore (D04, G02: alimentato dal polling, non piu' da un
    webhook HTTP) arriva al sink costruito da tunnel.costruisci_instradamento
    (D06), che lo spinge sulla sola linea aperta dell'installazione giusta
    del RegistroTunnel (D03/A05) risolvendo l'installazione dal pairing
    (D05)."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.registro = tunnel.RegistroTunnel()
        self.pairing = telegram_webhook.MemoriaPairing((42,))
        risolvi = lambda chat_id: "l-installazione" if chat_id == 42 else None
        sink = tunnel.costruisci_instradamento(risolvi, self.registro)
        self.gestore = telegram_webhook.GestoreWebhook(
            pairing=self.pairing, sink=sink,
            answer_callback=lambda callback_id: None)
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0,
                                              gestore_webhook=self.gestore, tunnel_token=self.TOKEN,
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
            f"{self.base_url}/tunnel?installation=l-installazione",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta_tunnel, timeout=5) as risposta:
            self.assertEqual(risposta.status, 200)
            for _ in range(200):
                if self.registro.push("l-installazione", {"kind": "probe"}):
                    break
                time.sleep(0.01)
            while risposta.readline().decode("utf-8").strip() != "":
                pass  # consuma l'intero frame di sondaggio prima del tap vero

            self.gestore.processa_update({"update_id": 1, "callback_query": {
                "id": "cb-1", "data": "il-token", "message": {"message_id": 5, "chat": {"id": 42}}}})

            righe = []
            while True:
                riga = risposta.readline().decode("utf-8")
                righe.append(riga)
                if riga.strip() == "" and any("data:" in r for r in righe):
                    break
            self.assertIn("event: tap\n", righe)
            self.assertTrue(any('"callback_data": "il-token"' in r for r in righe))


class InoltroTapConCallbackDataAccorciatoEndToEnd(unittest.TestCase):
    """D08 assemblato come farebbe atlas_relay.main(): un unico
    'capability_store.StoreCapability' condiviso fra l'endpoint di deliver
    (che registra il capability token e torna l'id corto) e il traduttore
    (G02: alimentato dal polling, che lo risolve appena prima del sink). Il
    capability token per intero non tocca mai Telegram: solo l'identificativo
    corto ci arriva, e solo quello torna indietro nel tap."""

    TOKEN = "il-bearer-del-tunnel"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.gestore_pairing.richiedi("la-macchina")
        self.gestore_pairing.richiedi_ingresso(codice, 42, "tester")
        self.gestore_pairing.approva(codice)

        self.registro = tunnel.RegistroTunnel()
        self.store = capability_store.StoreCapability()
        # 'installazioni_di' e' plurale (A02): qui basta la piu' recente,
        # come l'adattatore vero di atlas_relay.main() (A05).
        risolvi = lambda chat_id: next(iter(self.gestore_pairing.installazioni_di(chat_id)), None)
        sink = tunnel.costruisci_instradamento(risolvi, self.registro)
        self.gestore_webhook = telegram_webhook.GestoreWebhook(
            pairing=self.gestore_pairing, sink=sink,
            answer_callback=lambda callback_id: None, capability_resolver=self.store.preleva)
        self.chiamate_invia_bottoni = []
        self.server = atlas_relay.crea_server(
            host="127.0.0.1", port=0, gestore_webhook=self.gestore_webhook, tunnel_token=self.TOKEN,
            registro_tunnel=self.registro, gestore_pairing=self.gestore_pairing,
            invia_bottoni=lambda chat_id, testo, bottoni: self.chiamate_invia_bottoni.append(bottoni),
            capability_store=self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.fermo.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_il_capability_token_reale_torna_indietro_dopo_il_tap(self):
        import json

        capability_reale = "eyJ..." + "x" * 250  # >64 byte, come un token vero (D01/D07)
        richiesta_deliver = urllib.request.Request(
            f"{self.base_url}/tunnel/deliver",
            data=json.dumps({"installation": "la-macchina", "text": "Serve una decisione",
                             "buttons": [{"label": "Conferma", "data": capability_reale}]}).encode(),
            headers={"Authorization": f"Bearer {self.TOKEN}", "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(richiesta_deliver) as risposta:
            self.assertEqual(risposta.status, 200)
        identificativo_corto = self.chiamate_invia_bottoni[0][0][1]
        self.assertLessEqual(len(identificativo_corto.encode("utf-8")), 64)

        richiesta_tunnel = urllib.request.Request(
            f"{self.base_url}/tunnel?installation=la-macchina",
            headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta_tunnel, timeout=5) as risposta_tunnel:
            for _ in range(200):
                if self.registro.push("la-macchina", {"kind": "probe"}):
                    break
                time.sleep(0.01)
            while risposta_tunnel.readline().decode("utf-8").strip() != "":
                pass  # consuma l'intero frame di sondaggio prima del tap vero

            self.gestore_webhook.processa_update({"update_id": 1, "callback_query": {
                "id": "cb-1", "data": identificativo_corto,
                "message": {"message_id": 5, "chat": {"id": 42}}}})

            righe = []
            while True:
                riga = risposta_tunnel.readline().decode("utf-8")
                righe.append(riga)
                if riga.strip() == "" and any("data:" in r for r in righe):
                    break
            self.assertTrue(any(f'"callback_data": "{capability_reale}"' in r for r in righe))


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
        with self._post(json.dumps({"installation": "la-macchina"}).encode("utf-8")) as risposta:
            self.assertEqual(risposta.status, 200)
            corpo = json.loads(risposta.read())
        self.assertIn("code", corpo)
        self.assertEqual(corpo["url"], f"https://t.me/atlas_bot?start={corpo['code']}")
        self.assertIn("expiresAt", corpo)

    def test_richiedi_senza_bearer_401(self):
        import json
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(json.dumps({"installation": "la-macchina"}).encode("utf-8"), autorizzato=False)
        self.assertEqual(ctx.exception.code, 401)

    def test_richiedi_senza_installation_400(self):
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
                f"http://{host}:{port}/pairing",
                data=json.dumps({"installation": "la-macchina"}).encode("utf-8"),
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
        with self._post(json.dumps({"installation": "la-macchina"}).encode("utf-8")) as risposta:
            codice = json.loads(risposta.read())["code"]

        richiesta = urllib.request.Request(
            f"{self.base_url}/pairing?code={codice}", headers={"Authorization": f"Bearer {self.TOKEN}"})
        with urllib.request.urlopen(richiesta) as risposta:
            self.assertEqual(json.loads(risposta.read()), {"status": "in_attesa"})

        self.gestore.richiedi_ingresso(codice, 42, "tester")
        with urllib.request.urlopen(richiesta) as risposta:
            self.assertEqual(json.loads(risposta.read()), {"status": "in_attesa_gestore"})

        self.gestore.approva(codice)
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
    def __init__(self, readlink_stdout="/opt/atlas-relay/releases/0.0.0", salute_returncode=0):
        self.chiamate = []
        self.readlink_stdout = readlink_stdout
        self.salute_returncode = salute_returncode

    def __call__(self, argv, **kwargs):
        self.chiamate.append(argv)
        if "readlink" in argv:
            return FakeCompletedProcess(0, self.readlink_stdout)
        if "curl" in argv:
            return FakeCompletedProcess(self.salute_returncode)
        return FakeCompletedProcess(0)


class HealthCheck(unittest.TestCase):
    """G02: nessuna porta pubblica, il controllo passa da ssh verso la porta
    locale (127.0.0.1:8765) dello stesso host di deploy, mai da un opener
    HTTPS verso un hostname esposto."""

    ENV = PrerequisitiDeploy.ENV_COMPLETO

    def test_successo_al_primo_tentativo(self):
        runner = FakeRunner(salute_returncode=0)
        self.assertTrue(deploy.controlla_salute(self.ENV, tentativi=3, runner=runner, sleep=lambda s: None))

    def test_fallisce_dopo_n_tentativi(self):
        runner = FakeRunner(salute_returncode=1)
        attese = []
        ok = deploy.controlla_salute(self.ENV, tentativi=3, attesa=0.01, runner=runner,
                                      sleep=attese.append)
        self.assertFalse(ok)
        self.assertEqual(len(attese), 2)  # nessuna attesa dopo l'ultimo tentativo


class DeployRollback(unittest.TestCase):
    ENV = PrerequisitiDeploy.ENV_COMPLETO

    def test_health_ok_non_fa_rollback(self):
        runner = FakeRunner()
        deploy.deploy(self.ENV, "1.2.3", runner=runner, sleep=lambda s: None)
        comandi = [" ".join(c) for c in runner.chiamate]
        self.assertTrue(any("restart" in c for c in comandi))
        self.assertEqual(sum("ln" in c for c in comandi), 1)  # solo lo switch iniziale, nessun rollback

    def test_health_fallito_fa_rollback_e_solleva(self):
        runner = FakeRunner(readlink_stdout="/opt/atlas-relay/releases/0.0.0", salute_returncode=1)

        with self.assertRaises(RuntimeError) as ctx:
            deploy.deploy(self.ENV, "1.2.3", runner=runner, sleep=lambda s: None)
        self.assertIn("rollback", str(ctx.exception))
        comandi = [" ".join(c) for c in runner.chiamate]
        self.assertEqual(sum("ln" in c for c in comandi), 2)  # switch al nuovo + rollback al precedente
        self.assertEqual(sum("restart" in c for c in comandi), 2)  # restart dopo il deploy + dopo il rollback

    def test_health_fallito_senza_precedente_solleva_senza_rollback(self):
        runner = FakeRunner(readlink_stdout="", salute_returncode=1)

        with self.assertRaises(RuntimeError) as ctx:
            deploy.deploy(self.ENV, "1.2.3", runner=runner, sleep=lambda s: None)
        self.assertIn("nessun rilascio precedente", str(ctx.exception))

    def test_rifiuta_prima_di_toccare_qualunque_comando_se_mancano_prerequisiti(self):
        runner = FakeRunner()
        with self.assertRaises(deploy.PrerequisitiMancanti):
            deploy.deploy({}, "1.2.3", runner=runner)
        self.assertEqual(runner.chiamate, [])


if __name__ == "__main__":
    unittest.main()
