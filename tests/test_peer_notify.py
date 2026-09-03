"""Verifica peer_notify.avvisa (E01): come si compone la richiesta verso
/peers/notify e come si comporta senza relay configurato. Nessuna rete reale
nei test unitari ('opener' e' sempre un doppio finto); un giro end-to-end
verifica anche il lato relay vero (pairing incluso).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

from core import peer_notify, project_code, relay_identity  # noqa: E402
from core.config import Workspace  # noqa: E402

import atlas_relay  # noqa: E402
import pairing  # noqa: E402
import peers  # noqa: E402

TOKEN = "il-bearer-del-tunnel"


class _RispostaVuota:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class PeerNotifyTest(unittest.TestCase):
    def setUp(self):
        self._progetto = Path(tempfile.mkdtemp())
        self._install_home = Path(tempfile.mkdtemp())
        self.root = self._progetto / ".atlas"
        self.root.mkdir()
        self.ws = Workspace(self.root)

    def tearDown(self):
        shutil.rmtree(self._progetto)
        shutil.rmtree(self._install_home)

    def _env(self, **over):
        env = {"RELAY_HTTPS_HOSTNAME": "relay.test", "ATLAS_RELAY_TOKEN_REF": TOKEN,
              "ATLAS_INSTALL_HOME": str(self._install_home)}
        env.update(over)
        return env

    def _casa_vuota(self) -> str:
        """Un'installazione senza profilo di relay. Un ambiente vuoto non basta
        piu' a dire 'nessun relay': la configurazione vive anche su disco, e su
        una macchina che il relay ce l'ha davvero il test leggerebbe quello."""
        casa = tempfile.mkdtemp(prefix="atlas-test-senza-relay-")
        self.addCleanup(shutil.rmtree, casa, True)
        return casa

    def test_senza_relay_configurato_non_chiama_l_opener(self):
        chiamate = []
        peer_notify.avvisa(self.ws, env={"ATLAS_INSTALL_HOME": self._casa_vuota()},
                           opener=lambda *a, **k: chiamate.append(a))
        self.assertEqual(chiamate, [])

    def test_posta_bearer_codice_e_installazione(self):
        richieste = []

        def opener(richiesta, timeout=None):
            richieste.append(richiesta)
            return _RispostaVuota()

        env = self._env()
        peer_notify.avvisa(self.ws, env=env, opener=opener)
        self.assertEqual(len(richieste), 1)
        richiesta = richieste[0]
        self.assertEqual(richiesta.full_url, "https://relay.test/peers/notify")
        self.assertEqual(richiesta.get_header("Authorization"), f"Bearer {TOKEN}")
        corpo = json.loads(richiesta.data)
        codice = project_code.carica_o_crea(self.ws)
        installazione = relay_identity.carica_o_crea(env=env)
        self.assertEqual(corpo, {"projectCode": codice, "installation": installazione.installation_id})

    def test_relay_irraggiungibile_non_solleva(self):
        def opener(richiesta, timeout=None):
            raise OSError("rete giu'")

        peer_notify.avvisa(self.ws, env=self._env(), opener=opener)  # non solleva

    def test_due_avvisi_usano_lo_stesso_codice_di_progetto(self):
        richieste = []

        def opener(richiesta, timeout=None):
            richieste.append(richiesta)
            return _RispostaVuota()

        env = self._env()
        peer_notify.avvisa(self.ws, env=env, opener=opener)
        peer_notify.avvisa(self.ws, env=env, opener=opener)
        primo = json.loads(richieste[0].data)["projectCode"]
        secondo = json.loads(richieste[1].data)["projectCode"]
        self.assertEqual(primo, secondo)


class PeerNotifyEndToEnd(unittest.TestCase):
    """peer_notify.avvisa (client) contro il vero endpoint /peers/notify
    (relay, E01), pairing vero incluso: due installazioni condividono un
    codice di progetto, la seconda avvisa e la prima riceve il testo muto."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gestore_pairing = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.registro_peer = peers.RegistroPeer(Path(self.tmp.name) / "peers.json")
        self.messaggi = []
        avviso_peer = peers.costruisci_avviso(
            self.registro_peer, self.gestore_pairing.chat_id_di,
            lambda chat_id, testo: self.messaggi.append((chat_id, testo)))
        self.server = atlas_relay.crea_server(host="127.0.0.1", port=0, tunnel_token=TOKEN,
                                              gestore_pairing=self.gestore_pairing,
                                              avviso_peer=avviso_peer)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def _appaia(self, installation_id: str, chat_id: int) -> None:
        codice, _ = self.gestore_pairing.richiedi(installation_id)
        self.gestore_pairing.richiedi_ingresso(codice, chat_id, "tester")
        self.gestore_pairing.approva(codice)

    def _progetto_e_ambiente(self, installation_home: Path) -> tuple[Workspace, dict]:
        progetto = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, progetto, True)
        root = progetto / ".atlas"
        root.mkdir()
        ws = Workspace(root)
        env = {"RELAY_PUBLIC_URL": self.base_url, "ATLAS_RELAY_TOKEN_REF": TOKEN,
              "ATLAS_INSTALL_HOME": str(installation_home)}
        return ws, env

    def _forza_identita(self, install_home: Path, installation_id: str) -> None:
        """I due lati del pairing sono gia' fissati su 'mac-a'/'mac-b': qui si
        scrive direttamente il file che relay_identity.carica_o_crea legge,
        cosi' l'identita' generata dal client combacia con quella appaiata,
        invece di lasciarla nascere casuale e scollegata dal pairing."""
        install_home.mkdir(parents=True, exist_ok=True)
        (install_home / "relay-identity.json").write_text(
            json.dumps({"installationId": installation_id, "secret": "s"}), encoding="utf-8")

    def test_il_secondo_che_avvisa_sveglia_il_primo(self):
        self._appaia("mac-a", 42)
        self._appaia("mac-b", 43)
        ws_a, env_a = self._progetto_e_ambiente(Path(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, env_a["ATLAS_INSTALL_HOME"], True)
        self._forza_identita(Path(env_a["ATLAS_INSTALL_HOME"]), "mac-a")
        codice = project_code.carica_o_crea(ws_a)
        # mac-b lavora la stessa copia del progetto (stesso codice, gia'
        # committato) da un'altra installazione: si scrive lo stesso codice
        # nel suo config.json, esattamente come farebbe un git pull.
        ws_b, env_b = self._progetto_e_ambiente(Path(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, env_b["ATLAS_INSTALL_HOME"], True)
        self._forza_identita(Path(env_b["ATLAS_INSTALL_HOME"]), "mac-b")
        (ws_b.root / "config.json").write_text(json.dumps({"projectCode": codice}), encoding="utf-8")

        peer_notify.avvisa(ws_a, env=env_a, opener=urllib.request.urlopen)
        self.assertEqual(self.messaggi, [])   # nessun pari ancora: mac-a e' il primo

        peer_notify.avvisa(ws_b, env=env_b, opener=urllib.request.urlopen)
        self.assertEqual(self.messaggi, [(42, peers.TESTO_AVVISO)])

    def test_senza_pairing_configurato_e_404_assorbito_in_silenzio(self):
        server = atlas_relay.crea_server(host="127.0.0.1", port=0, tunnel_token=TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            ws, env = self._progetto_e_ambiente(Path(tempfile.mkdtemp()))
            self.addCleanup(shutil.rmtree, env["ATLAS_INSTALL_HOME"], True)
            env["RELAY_PUBLIC_URL"] = f"http://{host}:{port}"
            peer_notify.avvisa(ws, env=env, opener=urllib.request.urlopen)  # non solleva
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
