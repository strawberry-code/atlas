"""Verifica end-to-end del percorso Automata + Interazione + UI (E01).

Ogni nodo del grafo Interactions ha gia' una sua suite fitta in isolamento
(A03/A04 il lifecycle, A05 il risveglio, B03 l'HTTP, C01/C02/C03 gli avvisi,
D01-D06 relay e Telegram). Quello che nessuna di quelle prova e' l'incrocio:
un automata.execute() vero, in un thread, che si sblocca da un vero POST di
'atlas serve' in un altro thread, nello stesso processo (esattamente come
'atlas run' e 'atlas serve' insieme sulla stessa macchina); e cosa succede a
quel run quando il processo si ferma e un altro riparte, con o senza il nodo
HITL ancora aperto.
"""
from __future__ import annotations

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
from unittest import mock

SOURCE = Path(__file__).resolve().parent.parent / "payload"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".atlas"
        shutil.copytree(SOURCE, self.root)
        (self.root / "config.json").write_text('{"project": "prova"}', encoding="utf-8")
        for folder in ("graphs", "scripts"):
            (self.root / folder).mkdir()
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        for module in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[module]
        from core import automata, config, docs, mutate, serve, store

        self.automata = automata
        self.config = config
        self.docs = docs
        self.mutate = mutate
        self.serve = serve
        self.store = store
        self.workspace = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.workspace, "prova", "Grafo", "Verificare")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for module in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[module]
        shutil.rmtree(self.tmp)

    def _aggiungi_nodo_hitl(self, node_id="H01"):
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_branch(g, "B", "Ramo", "#0f766e")
            self.mutate.add_node(g, node_id, "Nodo umano", "B", "decidere", mode="HITL")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def _esegui_e_ignora_hitl(self, run):
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            try:
                run.execute(lambda r, n: None)
            except self.automata.RunnerError:
                pass

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

    def _url(self, server, path):
        return f"http://127.0.0.1:{server.server_address[1]}{path}"

    def _post(self, server, path):
        richiesta = urllib.request.Request(self._url(server, path), method="POST")
        return urllib.request.urlopen(richiesta, timeout=5)

    def _interactions(self):
        return self.store.load(self.ref.json_path)["interactions"]

    def _attendi_interaction_aperta(self, esclude=(), timeout=5):
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            nuove = [r for r in self._interactions() if r["id"] not in esclude]
            if nuove:
                return nuove[-1]["id"]
            time.sleep(0.05)
        self.fail("nessuna interaction aperta entro il timeout")


class RisoluzioneDalVeroServerHttp(Base):
    """A05 (Automata apre e attende) + B03 (Handler risolve via HTTP) nello
    stesso processo: e' lo scenario reale, senza alcuno stub sul lifecycle."""

    def test_un_run_vero_si_sblocca_da_un_vero_post_e_il_nodo_resta_a_un_umano(self):
        self._aggiungi_nodo_hitl()
        server = self._server()
        run = self.automata.start(self.ref, 1)
        runner = threading.Thread(target=self._esegui_e_ignora_hitl, args=(run,))
        runner.start()

        interaction_id = self._attendi_interaction_aperta()
        with self._post(server, f"/interactions/{interaction_id}/confirm") as risposta:
            self.assertEqual(200, risposta.status)
        runner.join(timeout=10)

        self.assertFalse(runner.is_alive(), "il run non si e' fermato dopo la risoluzione")
        record = next(r for r in self._interactions() if r["id"] == interaction_id)
        self.assertEqual("resolved", record["status"])
        self.assertEqual("resume", record["resolution"]["effect"])
        # La risoluzione sblocca il run, non chiude il nodo: quello resta a un umano.
        self.assertEqual("open", self.store.load(self.ref.json_path)["nodes"][0]["status"])

    def test_un_secondo_post_sulla_stessa_card_torna_409_col_run_ancora_appeso(self):
        self._aggiungi_nodo_hitl()
        server = self._server()
        run = self.automata.start(self.ref, 1)
        runner = threading.Thread(target=self._esegui_e_ignora_hitl, args=(run,))
        runner.start()
        self.addCleanup(runner.join, 10)

        interaction_id = self._attendi_interaction_aperta()
        with self._post(server, f"/interactions/{interaction_id}/confirm") as risposta:
            self.assertEqual(200, risposta.status)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(server, f"/interactions/{interaction_id}/confirm")
        self.assertEqual(409, ctx.exception.code)


class RiavvioDelProcesso(Base):
    """Cosa succede a run_state quando il processo che tiene Automata si
    ferma. Le due meta' non sono simmetriche: un crash a meta' attesa lascia
    lo stato a 'waiting' (non terminale) e il run successivo riprende lo
    stesso run_id, senza duplicare la card; uno stop pulito su una domanda
    HITL chiude invece run_state a 'failed' (terminale, vedi automata.execute
    e la stringa 'automata.hitl' che non contiene 'run bloccato'), quindi un
    riavvio prima di chiudere a mano il nodo apre un run_id nuovo e con lui
    una seconda card per lo stesso nodo."""

    def test_un_crash_a_meta_attesa_riprende_lo_stesso_run_un_riavvio_dopo_uno_stop_pulito_no(self):
        self._aggiungi_nodo_hitl()
        server = self._server()

        run1 = self.automata.start(self.ref, 1)
        runner1 = threading.Thread(target=self._esegui_e_ignora_hitl, args=(run1,))
        runner1.start()
        prima_id = self._attendi_interaction_aperta()

        # Un secondo processo che interrogasse Atlas ora (il primo e' ancora
        # appeso in attesa, come dopo un crash prima di una risposta) vedrebbe
        # run_state.json a 'waiting': non terminale, quindi 'resumable'.
        run_dopo_crash = self.automata.start(self.ref, 1)
        self.assertEqual(run1.run_state.run_id, run_dopo_crash.run_state.run_id,
                          "un crash mentre si attende la card non deve inventare un run nuovo")

        with self._post(server, f"/interactions/{prima_id}/confirm") as risposta:
            self.assertEqual(200, risposta.status)
        runner1.join(timeout=10)
        self.assertFalse(runner1.is_alive())
        self.assertEqual(1, len(self._interactions()),
                          "risolta mentre il run era vivo: nessuna seconda card")

        # Lo stop e' stato pulito (RunnerError su HITL): run_state ora e'
        # 'failed', terminale. Il nodo H01 resta pero' aperto (la risoluzione
        # sblocca il run, non lo chiude). Un secondo 'atlas run' lanciato
        # senza aver chiuso H01 a mano non riprende quel run_id.
        run3 = self.automata.start(self.ref, 1)
        self.assertNotEqual(run1.run_state.run_id, run3.run_state.run_id,
                             "dopo uno stop pulito il run_state e' terminale: non e' resumable")

        runner3 = threading.Thread(target=self._esegui_e_ignora_hitl, args=(run3,))
        runner3.start()
        seconda_id = self._attendi_interaction_aperta(esclude=(prima_id,))
        with self._post(server, f"/interactions/{seconda_id}/confirm") as risposta:
            self.assertEqual(200, risposta.status)
        runner3.join(timeout=10)

        interazioni = self._interactions()
        self.assertEqual(2, len(interazioni))
        self.assertEqual(["H01", "H01"], [r["nodeId"] for r in interazioni])
        self.assertEqual(["resolved", "resolved"], [r["status"] for r in interazioni])
        self.assertNotEqual(interazioni[0]["runId"], interazioni[1]["runId"])


if __name__ == "__main__":
    unittest.main()
