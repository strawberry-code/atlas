"""Test di 'atlas serve': la dashboard viva su un server locale.

Si prova il nocciolo (rigenerazione sull'mtime di graph.json) e la risposta
HTTP, senza rete e senza dipendenze: il server ascolta su 127.0.0.1, porta 0
(una porta libera), e le richieste si fanno con urllib della stdlib.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "payload"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".atlas"
        shutil.copytree(SORGENTE, self.root)
        (self.root / "config.json").write_text(json.dumps({"project": "prova"}), encoding="utf-8")
        for cartella in ("graphs", "scripts"):
            (self.root / cartella).mkdir()
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        from core import config, mutate, remotelock, render, serve, store
        self.config, self.mutate, self.render = config, mutate, render
        self.store, self.serve = store, serve
        self.remotelock = remotelock
        self.ws = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo di prova", "Verificare il serve.")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        shutil.rmtree(self.tmp)


class Rigenerazione(Base):
    def test_rigenera_quando_l_mtime_avanza_e_non_altrimenti(self):
        dash = self.serve.Dashboard(self.ref)
        self.assertTrue(dash.aggiorna())               # prima generazione
        self.assertIn("Grafo di prova", dash.html())
        self.assertFalse(dash.aggiorna())              # grafo invariato: niente da rifare
        # cambia il titolo e sposta l'mtime avanti in modo esplicito: la rigenerazione
        # deve scattare per l'mtime, non per il contenuto
        with self.store.transaction(self.ref.json_path) as data:
            data["meta"]["title"] = "Grafo nuovo"
        futuro = time.time() + 5
        os.utime(self.ref.json_path, (futuro, futuro))
        self.assertTrue(dash.aggiorna())
        self.assertIn("Grafo nuovo", dash.html())
        self.assertNotIn("Grafo di prova", dash.html())

    def test_non_rigenera_se_cambia_il_contenuto_ma_non_l_mtime(self):
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        prima = dash.html()
        vecchio = os.stat(self.ref.json_path).st_mtime     # l'mtime prima del cambio
        with self.store.transaction(self.ref.json_path) as data:
            data["meta"]["title"] = "Cambia solo il contenuto"
        os.utime(self.ref.json_path, (vecchio, vecchio))   # riporta l'orologio a prima
        self.assertFalse(dash.aggiorna())
        self.assertEqual(prima, dash.html())


class PortaProgetto(Base):
    def test_e_deterministica_e_nella_fascia_utente(self):
        porta = self.serve._porta_progetto(self.ref)
        self.assertEqual(porta, self.serve._porta_progetto(self.ref))
        self.assertTrue(self.serve._PORTA_MIN <= porta < self.serve._PORTA_MIN + self.serve._PORTA_RANGE)

    def test_grafi_diversi_danno_porte_diverse(self):
        altro = self.mutate.create_graph(self.ws, "altro", "Altro grafo", "Verificare la porta.")
        self.assertNotEqual(self.serve._porta_progetto(self.ref), self.serve._porta_progetto(altro))


class Http(Base):
    def _server(self):
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        server = self.serve.Server(("127.0.0.1", 0), self.serve.Handler)
        server.dash = dash
        server.spettatori = self.serve.Viewers()
        server.fermo = threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._ferma, server)
        return server

    def _ferma(self, server):
        server.fermo.set()
        server.shutdown()
        server.server_close()

    def _url(self, server, percorso="/"):
        return f"http://127.0.0.1:{server.server_address[1]}{percorso}"

    def test_la_dashboard_risponde_col_reload_iniettato(self):
        server = self._server()
        with urllib.request.urlopen(self._url(server), timeout=5) as risposta:
            self.assertEqual(200, risposta.status)
            self.assertEqual("text/html", risposta.headers.get_content_type())
            self.assertEqual("utf-8", risposta.headers.get_param("charset"))
            corpo = risposta.read().decode("utf-8")
        self.assertIn("Grafo di prova", corpo)
        self.assertIn("EventSource", corpo)      # il canale di ricarica c'e'
        self.assertIn("/events", corpo)

    def test_una_pagina_che_non_esiste_da_404(self):
        server = self._server()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url(server, "/mappa"), timeout=5)
        self.assertEqual(404, ctx.exception.code)

    def test_un_grafo_rotto_risponde_503_non_traceback(self):
        server = self._server()
        self.ref.json_path.write_text("{non-json", encoding="utf-8")
        futuro = time.time() + 5
        os.utime(self.ref.json_path, (futuro, futuro))
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url(server), timeout=5)
        self.assertEqual(503, ctx.exception.code)

    def test_il_canale_avvisa_il_browser_quando_il_grafo_cambia(self):
        """La spinta: un /events aperto riceve 'reload' quando l'mtime avanza."""
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        server = self.serve.Server(("127.0.0.1", 0), self.serve.Handler)
        server.dash = dash
        server.spettatori = self.serve.Viewers()
        server.fermo = threading.Event()
        guardia = threading.Thread(target=self.serve._watch, args=(server,), daemon=True)
        guardia.start()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._ferma, server)

        ricevuto = []

        def ascolta():
            with urllib.request.urlopen(self._url(server, "/events"), timeout=10) as r:
                for riga in r:
                    if riga.strip() == b"event: reload":
                        ricevuto.append(True)
                        return

        udito = threading.Thread(target=ascolta, daemon=True)
        udito.start()
        time.sleep(0.3)                        # lascia che l'ascoltatore si registri

        with self.store.transaction(self.ref.json_path) as data:
            data["meta"]["title"] = "Cambiato dal vivo"
        futuro = time.time() + 5
        os.utime(self.ref.json_path, (futuro, futuro))
        udito.join(timeout=5)
        self.assertTrue(ricevuto, "il canale /events non ha annunciato il reload")


class Azioni(Base):
    """POST /interactions/<id>/<action>: il pannello Notifiche parla col
    lifecycle atomico (A04) e con la ripresa di Autopilot (A05) solo da qui."""

    def _server(self):
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        server = self.serve.Server(("127.0.0.1", 0), self.serve.Handler)
        server.dash = dash
        server.spettatori = self.serve.Viewers()
        server.fermo = threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._ferma, server)
        return server

    def _ferma(self, server):
        server.fermo.set()
        server.shutdown()
        server.server_close()

    def _url(self, server, percorso):
        return f"http://127.0.0.1:{server.server_address[1]}{percorso}"

    def _post(self, server, percorso):
        richiesta = urllib.request.Request(self._url(server, percorso), method="POST")
        return urllib.request.urlopen(richiesta, timeout=5)

    def _apri_interaction(self):
        from core import interactions

        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, "A01", "Nodo", "A", "Domanda")
        with self.mutate.editing(self.ref) as g:
            record = interactions.open_interaction(
                g, run_id="run-01", node_id="A01", event="decision-required",
                summary="Serve una decisione per A01.",
                allowed_actions=[
                    {"id": "confirm", "label": "Conferma", "effect": "resume"},
                    {"id": "decline", "label": "Rifiuta", "effect": "cancel"},
                ],
                expires_at="2099-01-01T00:00:00+00:00",
                idempotency_key="run-01:A01:decision")
        return record["id"]

    def _record(self, interaction_id):
        from core.store import load
        return next(r for r in load(self.ref.json_path)["interactions"] if r["id"] == interaction_id)

    def test_un_azione_consentita_risolve_l_interaction_nel_ledger(self):
        interaction_id = self._apri_interaction()
        server = self._server()

        with self._post(server, f"/interactions/{interaction_id}/confirm") as risposta:
            self.assertEqual(200, risposta.status)
            self.assertEqual({"ok": True}, json.loads(risposta.read()))
        self.assertEqual("resolved", self._record(interaction_id)["status"])

    def test_un_azione_non_dichiarata_torna_409_senza_toccare_il_ledger(self):
        interaction_id = self._apri_interaction()
        server = self._server()

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(server, f"/interactions/{interaction_id}/acknowledge")
        self.assertEqual(409, ctx.exception.code)
        self.assertEqual("open", self._record(interaction_id)["status"])

    def test_il_secondo_invio_trova_la_card_gia_chiusa(self):
        interaction_id = self._apri_interaction()
        server = self._server()

        with self._post(server, f"/interactions/{interaction_id}/confirm") as risposta:
            self.assertEqual(200, risposta.status)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(server, f"/interactions/{interaction_id}/confirm")
        self.assertEqual(409, ctx.exception.code)

    def test_un_id_di_interaction_inesistente_torna_409_non_traceback(self):
        server = self._server()

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(server, "/interactions/I999/confirm")
        self.assertEqual(409, ctx.exception.code)

    def test_un_percorso_malformato_da_404(self):
        server = self._server()

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(server, "/interactions/I001")
        self.assertEqual(404, ctx.exception.code)

    def test_la_risoluzione_risveglia_chi_aspetta_in_process(self):
        """Collega il pannello alla ripresa di Autopilot: resolve_interaction
        dentro mutate.editing pubblica il ResolutionEvent che sblocca
        wait_for_resolution, lo stesso meccanismo che usa il runner (A05)."""
        from core import interactions

        interaction_id = self._apri_interaction()
        server = self._server()

        risultato = []

        def aspetta():
            risultato.append(interactions.wait_for_resolution(self.ref.slug, "run-01", timeout=5))

        ascolta = threading.Thread(target=aspetta)
        ascolta.start()
        time.sleep(0.2)   # lascia che wait_for_resolution si metta in coda

        with self._post(server, f"/interactions/{interaction_id}/confirm") as risposta:
            self.assertEqual(200, risposta.status)
        ascolta.join(timeout=5)

        self.assertEqual(1, len(risultato))
        self.assertIsNotNone(risultato[0])
        self.assertEqual(interaction_id, risultato[0].interaction_id)


class Pairing(Base):
    """POST/GET /pairing/telegram*: 'atlas serve' fa da tramite verso il relay
    (D05), il browser non parla mai col relay direttamente. La logica vera di
    serve_pairing.avvia/stato e' gia' testata in isolamento in
    tests/test_serve_pairing.py: qui si controlla solo che Handler la chiami e
    traduca il risultato in JSON."""

    def _server(self):
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        server = self.serve.Server(("127.0.0.1", 0), self.serve.Handler)
        server.dash = dash
        server.spettatori = self.serve.Viewers()
        server.fermo = threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._ferma, server)
        return server

    def _ferma(self, server):
        server.fermo.set()
        server.shutdown()
        server.server_close()

    def _url(self, server, percorso):
        return f"http://127.0.0.1:{server.server_address[1]}{percorso}"

    def test_avvia_chiama_serve_pairing_e_torna_il_suo_json(self):
        from core import serve_pairing

        chiamate = []
        originale = serve_pairing.avvia

        def finto(env=None, opener=None):
            chiamate.append(True)
            return 200, {"ok": True, "url": "https://t.me/atlas_bot?start=abc", "code": "abc"}

        serve_pairing.avvia = finto
        self.addCleanup(setattr, serve_pairing, "avvia", originale)

        server = self._server()
        richiesta = urllib.request.Request(self._url(server, "/pairing/telegram"), method="POST")
        with urllib.request.urlopen(richiesta) as risposta:
            self.assertEqual(risposta.status, 200)
            self.assertEqual(json.loads(risposta.read()),
                              {"ok": True, "url": "https://t.me/atlas_bot?start=abc", "code": "abc"})
        self.assertEqual(chiamate, [True])

    def test_avvia_senza_relay_configurato_torna_503(self):
        from core import serve_pairing

        originale = serve_pairing.avvia
        serve_pairing.avvia = lambda env=None, opener=None: (503, {"ok": False})
        self.addCleanup(setattr, serve_pairing, "avvia", originale)

        server = self._server()
        richiesta = urllib.request.Request(self._url(server, "/pairing/telegram"), method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(richiesta)
        self.assertEqual(ctx.exception.code, 503)

    def test_stato_passa_il_codice_dalla_querystring(self):
        from core import serve_pairing

        chiamate = []
        originale = serve_pairing.stato

        def finto(codice, env=None, opener=None):
            chiamate.append(codice)
            return 200, {"ok": True, "status": "associato"}

        serve_pairing.stato = finto
        self.addCleanup(setattr, serve_pairing, "stato", originale)

        server = self._server()
        with urllib.request.urlopen(self._url(server, "/pairing/telegram/status?code=abc123")) as risposta:
            self.assertEqual(risposta.status, 200)
            self.assertEqual(json.loads(risposta.read()), {"ok": True, "status": "associato"})
        self.assertEqual(chiamate, ["abc123"])


class Muto(Base):
    """POST /notify/telegram/toggle: la levetta per progetto di SS7-ter/1,
    dal pannello Notifiche al config.json del progetto servito."""

    def _server(self):
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        server = self.serve.Server(("127.0.0.1", 0), self.serve.Handler)
        server.dash = dash
        server.spettatori = self.serve.Viewers()
        server.fermo = threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._ferma, server)
        return server

    def _ferma(self, server):
        server.fermo.set()
        server.shutdown()
        server.server_close()

    def _url(self, server, percorso):
        return f"http://127.0.0.1:{server.server_address[1]}{percorso}"

    def _post(self, server, percorso):
        richiesta = urllib.request.Request(self._url(server, percorso), method="POST")
        return urllib.request.urlopen(richiesta, timeout=5)

    def test_il_toggle_spegne_poi_riaccende_e_torna_lo_stato_nuovo(self):
        server = self._server()
        with self._post(server, "/notify/telegram/toggle") as risposta:
            self.assertEqual(200, risposta.status)
            self.assertEqual({"ok": True, "enabled": False}, json.loads(risposta.read()))
        with self._post(server, "/notify/telegram/toggle") as risposta:
            self.assertEqual({"ok": True, "enabled": True}, json.loads(risposta.read()))

    def test_il_toggle_scrive_sul_config_json_del_progetto_servito(self):
        server = self._server()
        with self._post(server, "/notify/telegram/toggle"):
            pass
        dati = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(False, dati["notify"]["telegram_enabled"])
        self.assertEqual("prova", dati["project"])   # le altre chiavi restano


class StubTrasporto:
    """Il trasporto finto per la vista: elenca() conta le chiamate e risponde con
    l'elenco che gli si da' (o Rete, o vuoto). Gli altri metodi del protocollo non
    servono alla vista e non vengono toccati da serve.py."""

    def __init__(self, elenco=None, rete=False):
        self._elenco = elenco if elenco is not None else []
        self._rete = rete
        self.chiamate = 0

    def elenca(self):
        from core.remotelock import RETE, Esito
        self.chiamate += 1
        if self._rete:
            return Esito(RETE)
        return self._elenco

    def acquire(self, *a):
        return self._disattivo()

    def ruba(self, *a):
        return self._disattivo()

    def rilascia(self, *a):
        return self._disattivo()

    def rinnova(self, *a):
        return self._disattivo()

    def stato(self, *a):
        return self._disattivo()

    def _disattivo(self):
        from core.remotelock import DISATTIVO, Esito
        return Esito(DISATTIVO)


class LucchettiRemoti(Base):
    """La vista dei lucchetti delle altre macchine e il passo con cui si leggono."""

    def _un_esito(self, id_nodo, host, fresco: bool):
        from core.remotelock import TENUTO, Esito
        scadenza = int(time.time()) + (3600 if fresco else -60)
        return Esito(TENUTO, host=host, scadenza=scadenza, nome=f"{self.ref.slug}/{id_nodo}")

    def _url(self, server, percorso="/"):
        return f"http://127.0.0.1:{server.server_address[1]}{percorso}"

    def _ferma(self, server):
        server.fermo.set()
        server.shutdown()
        server.server_close()

    def _server(self, dash):
        server = self.serve.Server(("127.0.0.1", 0), self.serve.Handler)
        server.dash = dash
        server.spettatori = self.serve.Viewers()
        server.fermo = threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._ferma, server)
        return server

    def test_spento_la_vista_resta_quella_di_oggi(self):
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        self.assertFalse(self.remotelock.attivo())     # nessun trasporto iniettato
        self.assertFalse(dash.aggiorna_remoto())       # spento: non legge neanche
        self.assertNotIn("Lucchetti remoti", dash.html())

    def test_attivo_mostra_chi_tiene_cosa(self):
        self.remotelock.set_trasporto(StubTrasporto([
            self._un_esito("V02", "macchina-b", fresco=True),
            self._un_esito("A04", "macchina-c", fresco=False),
        ]))
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        self.assertTrue(dash.aggiorna_remoto())        # la prima lettura cambia la vista
        dash.aggiorna()
        html = dash.html()
        self.assertIn("Lucchetti remoti", html)
        self.assertIn("V02", html)
        self.assertIn("macchina-b", html)
        self.assertIn("macchina-c", html)
        self.assertIn("scaduto", html)                 # A04 ha la ref scaduta

    def test_attivo_senza_lucchetti_mostra_il_pannello_vuoto(self):
        self.remotelock.set_trasporto(StubTrasporto([]))
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        dash.aggiorna_remoto()
        dash.aggiorna()
        html = dash.html()
        self.assertIn("Lucchetti remoti", html)
        self.assertIn("nessun lucchetto remoto", html)

    def test_la_lettura_rispetta_il_passo_dichiarato(self):
        stub = StubTrasporto([])
        self.remotelock.set_trasporto(stub)
        self.serve.PASSO_REMOTO = 0.2
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        self.assertTrue(dash.aggiorna_remoto())        # prima lettura
        self.assertFalse(dash.aggiorna_remoto())       # dentro la finestra: non rilegge
        self.assertEqual(1, stub.chiamate)
        time.sleep(0.25)
        dash.aggiorna_remoto()                         # oltre il passo: rilegge
        self.assertEqual(2, stub.chiamate)

    def test_le_richieste_http_non_parlano_col_remote(self):
        """Il pannello si semina con una lettura, poi le richieste lo servono senza
        interrogare il remote: elenca() non scatta a ogni pagina servita."""
        stub = StubTrasporto([self._un_esito("V02", "macchina-b", fresco=True)])
        self.remotelock.set_trasporto(stub)
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        dash.aggiorna_remoto()                         # semina: la vista nasce coi lucchetti
        dash.aggiorna()
        server = self._server(dash)
        for _ in range(2):
            with urllib.request.urlopen(self._url(server), timeout=5) as risposta:
                self.assertIn("macchina-b", risposta.read().decode("utf-8"))
        self.assertEqual(1, stub.chiamate)             # solo la semina, mai le richieste

    def test_remote_irraggiungibile_degrada_senza_spammare(self):
        stub = StubTrasporto(rete=True)
        self.remotelock.set_trasporto(stub)
        self.serve.PASSO_REMOTO = 0.2
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        self.assertTrue(dash.aggiorna_remoto())        # primo errore: si annota
        dash.aggiorna()
        self.assertIn("remote non raggiungibile", dash.html())
        self.assertFalse(dash.aggiorna_remoto())       # errore ripetuto: niente da annunciare
        self.assertFalse(dash.aggiorna())              # e niente da rigenerare
        # il remote torna: la vista si riallinea e l'avviso sparisce
        stub._rete = False
        stub._elenco = [self._un_esito("V02", "macchina-b", fresco=True)]
        time.sleep(0.25)
        self.assertTrue(dash.aggiorna_remoto())
        dash.aggiorna()
        html = dash.html()
        self.assertIn("macchina-b", html)
        self.assertNotIn("remote non raggiungibile", html)

    def test_il_canale_avvisa_quando_cambiano_i_lucchetti_remoti(self):
        """La spinta end-to-end: un /events aperto riceve 'reload' quando la verita'
        remota cambia, come per il grafo."""
        stub = StubTrasporto([self._un_esito("F01", "macchina-a", fresco=True)])
        self.remotelock.set_trasporto(stub)
        self.serve.PASSO_REMOTO = 0.15
        self.serve.INTERVALLO = 0.15
        dash = self.serve.Dashboard(self.ref)
        dash.aggiorna()
        dash.aggiorna_remoto()                         # prima lettura: il pannello nasce pieno
        dash.aggiorna()
        server = self.serve.Server(("127.0.0.1", 0), self.serve.Handler)
        server.dash = dash
        server.spettatori = self.serve.Viewers()
        server.fermo = threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._ferma, server)

        ricevuto = []

        def ascolta():
            with urllib.request.urlopen(self._url(server, "/events"), timeout=10) as r:
                for riga in r:
                    if riga.strip() == b"event: reload":
                        ricevuto.append(True)
                        return

        udito = threading.Thread(target=ascolta, daemon=True)
        udito.start()
        time.sleep(0.3)                                # lascia che l'ascoltatore si registri
        guardia = threading.Thread(target=self.serve._watch, args=(server,), daemon=True)
        guardia.start()
        time.sleep(0.4)                                # la ronda fa una lettura senza cambi

        stub._elenco = [
            self._un_esito("F01", "macchina-a", fresco=True),
            self._un_esito("V02", "macchina-b", fresco=True),
        ]
        udito.join(timeout=5)
        self.assertTrue(ricevuto, "il canale /events non ha annunciato il cambio dei lucchetti remoti")


if __name__ == "__main__":
    unittest.main()
