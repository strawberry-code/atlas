"""Test del motore: forma del grafo, lucchetti, artefatti derivati.

Ogni test lavora su una copia fresca di payload/ in una cartella temporanea, cosi'
prova esattamente il codice che finisce dentro un progetto ospite.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

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
        from core import (config, docs, doctor, howto, identity, mutate, render, render_panels,
                          store, model, topology, claims, strings, report)
        self.config, self.docs, self.mutate = config, docs, mutate
        self.render, self.store, self.model, self.claims = render, store, model, claims
        self.strings, self.report, self.howto, self.doctor = strings, report, howto, doctor
        self.topology, self.identity, self.render_panels = topology, identity, render_panels
        self.ws = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo di prova", "Verificare il motore.")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        # I moduli 'core' caricati qui puntano alla sandbox che sta per sparire: lasciarli
        # in sys.modules rompe chi importa core dopo di noi, per esempio i test del CLI.
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        shutil.rmtree(self.tmp)

    def popola(self, **kwargs):
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_branch(g, "F", "Fondamenta", "#4f46e5")
            self.mutate.add_node(g, id="F01", branch="F", title="Primo", question="?")
            self.mutate.add_node(g, id="F02", branch="F", title="Secondo", question="?", blockedBy=["F01"])
            self.mutate.add_node(g, id="F03", branch="F", title="Terzo", question="?", blockedBy=["F02"])
        return self.store.load(self.ref.json_path)

    def rispondi(self, node_id: str):
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))
        path = self.ref.ticket_path(node_id)
        path.write_text(path.read_text(encoding="utf-8") + "\nLa risposta.\n", encoding="utf-8")

    def git_init(self):
        """La sandbox diventa una repo con un commit: serve ai test sulla deduzione
        degli artefatti, che guarda quel che e' cambiato rispetto a HEAD."""
        for comando in (["init"], ["config", "user.email", "prova@locale"], ["config", "user.name", "Prova"],
                        ["add", "."], ["commit", "-m", "primo"]):
            subprocess.run(["git", *comando], cwd=self.tmp, check=True, capture_output=True)


class Forma(Base):
    def test_frontiera_solo_i_nodi_sbloccati(self):
        data = self.popola()
        self.assertEqual(["F01"], [n["id"] for n in self.model.frontier(data)])

    def test_livelli_topologici(self):
        data = self.popola()
        self.assertEqual({"F01": 0, "F02": 1, "F03": 2}, self.topology.levels(data))

    def test_ciclo_rifiutato_e_grafo_intatto(self):
        self.popola()
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.link(g, "F01", blocked_by="F03")
        self.assertEqual([], self.store.load(self.ref.json_path)["nodes"][0]["blockedBy"])

    def test_arco_verso_nodo_inesistente(self):
        self.popola()
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.add_node(g, id="Z9", branch="F", title="X", question="?", blockedBy=["MAI"])

    def test_vocabolario_chiuso(self):
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.add_branch(g, "F", "Fondamenta")
                self.mutate.add_node(g, id="F01", branch="F", title="X", question="?", type="epico")

    def test_id_duplicato(self):
        self.popola()
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.add_node(g, id="F01", branch="F", title="Bis", question="?")

    def test_eccezione_nello_script_non_scrive(self):
        self.popola()
        with self.assertRaises(RuntimeError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.add_node(g, id="F04", branch="F", title="Perduto", question="?")
                raise RuntimeError("a metà")
        self.assertEqual(3, len(self.store.load(self.ref.json_path)["nodes"]))

    def test_fuori_scopo_sblocca_chi_aspettava(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.drop(g, "F01", reason="non serve più")
        data = self.store.load(self.ref.json_path)
        self.assertEqual(["F02"], [n["id"] for n in self.model.frontier(data)])
        self.assertEqual(1, len(data["outOfScope"]))

    def test_campi_protetti_non_si_toccano_da_mutate(self):
        self.popola()
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.edit_node(g, "F01", status="closed")

    def test_downstream_conta_tutti_i_dipendenti(self):
        data = self.popola()
        self.assertEqual({"F02", "F03"}, self.topology.downstream(data, "F01"))

    def test_cammino_residuo_fino_al_terminale(self):
        data = self.popola()
        self.assertEqual(2, self.topology.residual_path(data, "F01"))
        self.assertEqual(0, self.topology.residual_path(data, "F03"))

    def test_convergence_trova_finale_e_rami_sciolti(self):
        data = self.popola()
        self.assertEqual(("F03", []), self.topology.convergence(data))
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F03", blocked_by="F02")
        data = self.store.load(self.ref.json_path)
        self.assertEqual(("F02", ["F03"]), self.topology.convergence(data))

    def _arco_fantasma(self):
        """Un graph.json che nomina un blocker inesistente, come dopo un merge mal
        risolto o una modifica a mano: lo scrive direttamente, perche' mutate
        rifiuterebbe di produrlo."""
        self.popola()
        dati = json.loads(self.ref.json_path.read_text(encoding="utf-8"))
        dati["nodes"][1]["blockedBy"] = ["FANTASMA"]
        self.ref.json_path.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")

    def test_arco_fantasma_diagnosticato_non_esploso(self):
        """Il difetto deve uscire come diagnosi leggibile, non come KeyError nudo:
        e' lo stesso messaggio che darebbe 'validate', perche' il difetto e' quello."""
        self._arco_fantasma()
        data = self.store.load(self.ref.json_path)
        for nome, funzione in (("levels", self.topology.levels), ("frontier", self.model.frontier),
                               ("blocked", self.model.blocked), ("convergence", self.topology.convergence)):
            with self.subTest(funzione=nome):
                with self.assertRaises(self.store.StateError) as caso:
                    funzione(data)
                self.assertIn("FANTASMA", str(caso.exception))
                self.assertIn("F02", str(caso.exception))

    def test_ciclo_resta_diagnosticato(self):
        self.popola()
        dati = json.loads(self.ref.json_path.read_text(encoding="utf-8"))
        dati["nodes"][0]["blockedBy"] = ["F03"]        # F01 -> F02 -> F03 -> F01
        self.ref.json_path.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(self.store.StateError) as caso:
            self.topology.levels(self.store.load(self.ref.json_path))
        self.assertIn("ciclo", str(caso.exception).lower())

    def test_convergence_ignora_i_fuori_scopo(self):
        """Un ramo messo fuori scopo e' stato tagliato apposta: non e' sciolto."""
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F03", blocked_by="F02")
            self.mutate.drop(g, "F03", "ramo morto")
        data = self.store.load(self.ref.json_path)
        self.assertEqual(("F02", []), self.topology.convergence(data))

    def test_ranked_frontier_ordina_per_impatto(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F02", blocked_by="F01")
        data = self.store.load(self.ref.json_path)
        ordinata = self.topology.ranked_frontier(data)
        self.assertEqual(["F02", "F01"], [n["id"] for n, _, _ in ordinata])


class Lucchetti(Base):
    def test_due_ignoti_non_sono_lo_stesso_agente(self):
        """Fuori da una sessione Claude, e senza ATLAS_IDENTITY, l'identita' e' '?'.
        Prima due processi qualsiasi si riconoscevano come lo stesso attore: il
        secondo claim sullo stesso nodo tornava 'rivendicato' e rinfrescava il
        lucchetto del primo, cosi' due agenti lavoravano lo stesso nodo."""
        self.popola()
        senza_sessione = {k: v for k, v in os.environ.items()
                          if k not in ("CLAUDE_PID", "ATLAS_IDENTITY")}
        with mock.patch.dict(os.environ, senza_sessione, clear=True):
            os.environ["ATLAS_ROOT"] = str(self.root)
            self.claims.claim(self.ref, "F01", assignee="agente-uno")
            with self.assertRaises(self.store.StateError):
                self.claims.claim(self.ref, "F01", assignee="agente-due")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("agente-uno", nodo["assignee"], "il nodo resta di chi lo ha preso per primo")

    def test_identita_dichiarata_resta_riconoscibile(self):
        """La cura non deve rompere il caso legittimo: chi si dichiara si riconosce,
        quindi il secondo claim dello stesso attore rinfresca il proprio lucchetto."""
        self.popola()
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "esecutore-1"}):
            self.claims.claim(self.ref, "F01")
            self.claims.claim(self.ref, "F01")        # idempotente per lo stesso attore
            with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "esecutore-2"}):
                with self.assertRaises(self.store.StateError):
                    self.claims.claim(self.ref, "F01")

    def test_ciclo_di_vita(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        data = self.store.load(self.ref.json_path)
        self.assertEqual("claimed", self.model.node_of(data, "F01")["status"])
        self.claims.release(self.ref, "F01")
        self.assertEqual("open", self.model.node_of(self.store.load(self.ref.json_path), "F01")["status"])

    def test_non_si_rivendica_un_nodo_bloccato(self):
        self.popola()
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F02")

    def test_tetto_di_un_nodo_per_sessione(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F02", blocked_by="F01")
        self.claims.claim(self.ref, "F01")
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F02")

    def test_close_pretende_la_risposta_scritta(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        with self.assertRaises(self.store.StateError):
            self.claims.close(self.ref, "F01", "sintesi")
        self.rispondi("F01")
        node, _ = self.claims.close(self.ref, "F01", "sintesi")
        self.assertEqual("closed", node["status"])
        self.assertIn("closedAt", node)

    def test_close_registra_il_costo_se_dichiarato(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.rispondi("F01")
        node, _ = self.claims.close(self.ref, "F01", "sintesi", cost="~40 chiamate")
        self.assertEqual("~40 chiamate", node["cost"])

    def test_close_registra_gli_artifacts_se_dichiarati(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.rispondi("F01")
        node, _ = self.claims.close(self.ref, "F01", "sintesi", artifacts=["a.py", "b.py"])
        self.assertEqual(["a.py", "b.py"], node["artifacts"])

    def test_lucchetto_orfano(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        with self.store.transaction(self.ref.json_path) as data:
            self.model.node_of(data, "F01")["claim"]["pid"] = 999999
        node = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("dead", self.claims.claim_state(node, self.ws.config["agent"]))

    def test_identita_sovrascrivibile_permette_claim_paralleli(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F02", blocked_by="F01")
        os.environ["ATLAS_IDENTITY"] = "esecutore-1"
        try:
            self.claims.claim(self.ref, "F01")
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)
        os.environ["ATLAS_IDENTITY"] = "esecutore-2"
        try:
            self.claims.claim(self.ref, "F02")
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)
        data = self.store.load(self.ref.json_path)
        self.assertEqual("claimed", self.model.node_of(data, "F01")["status"])
        self.assertEqual("claimed", self.model.node_of(data, "F02")["status"])

    def test_riclamare_il_proprio_nodo_rinfresca_il_lucchetto(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        node = self.claims.claim(self.ref, "F01")
        self.assertEqual("claimed", node["status"])

    def test_riclamare_da_unaltra_identita_solleva(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        os.environ["ATLAS_IDENTITY"] = "qualcun-altro"
        try:
            with self.assertRaises(self.store.StateError):
                self.claims.claim(self.ref, "F01")
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)

    def test_rilascio_con_ragione_registra_levento(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.claims.release(self.ref, "F01", "non pronto")
        data = self.store.load(self.ref.json_path)
        self.assertEqual(1, len(data["releases"]))
        self.assertEqual("non pronto", data["releases"][0]["reason"])

    def test_flag_identity_vince_su_variabile_ambiente(self):
        self.popola()
        os.environ["ATLAS_IDENTITY"] = "env-identity"
        try:
            from core.cli import main
            argv = ["claim", "F01", "--identity", "flag-identity"]
            result = main(argv)
            self.assertEqual(0, result)
            data = self.store.load(self.ref.json_path)
            node = self.model.node_of(data, "F01")
            self.assertEqual("flag-identity", node["claim"]["identity"])
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)


class LucchettiWindows(Base):
    """identity.alive() sul ramo win32: os.kill(pid, 0) su Windows non e' un probe innocuo
    (per segnali diversi da CTRL_C/CTRL_BREAK la libc chiama TerminateProcess), quindi
    quel ramo deve passare da tasklist e non deve mai toccare os.kill."""

    def test_processo_vivo_non_chiama_mai_os_kill(self):
        with mock.patch("sys.platform", "win32"), \
             mock.patch("os.kill", side_effect=AssertionError("os.kill ucciderebbe il processo su Windows")), \
             mock.patch.object(self.identity, "subprocess") as sub:
            sub.run.return_value.stdout = '"claude.exe","4242","Console","1","10.000 K"\r\n'
            self.assertTrue(self.identity.alive(4242, "claude"))

    def test_processo_assente(self):
        with mock.patch("sys.platform", "win32"), \
             mock.patch.object(self.identity, "subprocess") as sub:
            sub.run.return_value.stdout = "INFO: No tasks are running which match the specified criteria.\r\n"
            self.assertFalse(self.identity.alive(4242, "claude"))


class Artefatti(Base):
    def render_tutto(self):
        data = self.store.load(self.ref.json_path)
        self.docs.ensure_map(self.ref, data)
        self.docs.write_stubs(self.ref, data)
        self.docs.rewrite_lists(self.ref, data)
        self.render.write(self.ref, data)
        return data

    def test_mappa_stabile_dopo_render_ripetuti(self):
        self.popola()
        self.render_tutto()
        primo = self.ref.map_path.read_text(encoding="utf-8")
        self.render_tutto()
        self.render_tutto()
        self.assertEqual(primo, self.ref.map_path.read_text(encoding="utf-8"))

    def test_decisioni_ricostruite_dal_grafo(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        _, _ = self.claims.close(self.ref, "F01", "così si è deciso")
        self.ref.map_path.unlink(missing_ok=True)
        self.render_tutto()
        self.assertIn("così si è deciso", self.ref.map_path.read_text(encoding="utf-8"))

    def test_rilascio_con_ragione_appare_nelle_decisioni(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.claims.release(self.ref, "F01", "verifica reale bocciata")
        self.render_tutto()
        self.assertIn("verifica reale bocciata", self.ref.map_path.read_text(encoding="utf-8"))

    def test_sezione_rinominata_fallisce_rumorosamente(self):
        data = self.popola()
        self.docs.ensure_map(self.ref, data)
        testo = self.ref.map_path.read_text(encoding="utf-8").replace("## Fuori scopo", "## Escluso")
        self.ref.map_path.write_text(testo, encoding="utf-8")
        with self.assertRaises(self.store.StateError):
            self.docs.rewrite_lists(self.ref, data)

    def test_ticket_non_sovrascritti(self):
        data = self.popola()
        self.docs.write_stubs(self.ref, data)
        self.ref.ticket_path("F01").write_text("scritto a mano", encoding="utf-8")
        self.assertEqual(0, self.docs.write_stubs(self.ref, data))
        self.assertEqual("scritto a mano", self.ref.ticket_path("F01").read_text(encoding="utf-8"))

    def test_dashboard_autoconsistente(self):
        """Autoconsistente = si apre da disco senza rete: script e stile viaggiano
        inline, i ticket incorporati come JSON, e nessun tag carica da fuori."""
        self.popola()
        self.render_tutto()
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertNotIn("<link", html)
        self.assertNotIn(" src=", html)
        self.assertNotIn('href="http', html)   # gli xmlns SVG contengono http://, i tag che caricano no
        self.assertIn('charset="utf-8"', html)
        self.assertIn('id="atlas-data"', html)
        self.assertEqual(3, html.count('class="card"'))
        for url in ("cdn", "googleapis", "unpkg"):
            self.assertNotIn(url, html)

    def test_dashboard_regge_un_grafo_vuoto(self):
        self.render_tutto()
        self.assertIn("<svg", self.ref.dashboard_path.read_text(encoding="utf-8"))

    def test_dashboard_avvisa_se_il_grafo_non_converge(self):
        self.popola()
        self.render_tutto()
        self.assertNotIn('class="blocco caution"', self.ref.dashboard_path.read_text(encoding="utf-8"))
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F03", blocked_by="F02")
        self.render_tutto()
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn('class="blocco caution"', html)
        self.assertIn('<b data-node="F03">F03</b>', html)

    def test_dashboard_mostra_il_costo_dichiarato(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        _, _ = self.claims.close(self.ref, "F01", "fatto", cost="~40 chiamate")
        self.render_tutto()
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn("~40 chiamate", html)

    def test_dashboard_regge_un_costo_senza_cifre(self):
        """La punteggiatura di un costo in prosa non deve far saltare il render."""
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        _, _ = self.claims.close(self.ref, "F01", "fatto", cost="Una sessione lunga... .")
        self.render_tutto()
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn("Una sessione lunga", html)

    def test_costo_numerico_estrae_solo_numeri_veri(self):
        casi = {"~40 chiamate": 40.0, "circa 1.5 ore": 1.5, "1,5 ore": 1.5,
                "15k token": 15.0, "Una sessione... .": None, "a occhio": None}
        for testo, atteso in casi.items():
            with self.subTest(testo=testo):
                self.assertEqual(self.render_panels._costo_numerico(testo), atteso)

    def prepara_lavoro(self):
        """Un nodo rivendicato in una repo git, con un file di lavoro appena scritto."""
        self.popola()
        self.rispondi("F01")
        self.git_init()
        self.claims.claim(self.ref, "F01")
        (self.tmp / "prodotto.txt").write_text("output", encoding="utf-8")

    def test_artifacts_dedotti_da_git_senza_flag(self):
        self.prepara_lavoro()
        node, _ = self.claims.close(self.ref, "F01", "fatto")
        self.assertIn("prodotto.txt", node["artifacts"])
        self.assertFalse([p for p in node["artifacts"] if p.startswith(".atlas/")])

    def test_artifacts_espliciti_vincono_sulla_deduzione(self):
        self.prepara_lavoro()
        node, _ = self.claims.close(self.ref, "F01", "fatto", artifacts=["esplicito.txt"])
        self.assertEqual(["esplicito.txt"], node["artifacts"])

    def test_artifacts_lista_vuota_svuota_il_campo(self):
        self.prepara_lavoro()
        node, _ = self.claims.close(self.ref, "F01", "fatto", artifacts=[])
        self.assertEqual([], node["artifacts"])

    def test_artifacts_non_dedotti_fuori_da_una_repo_git(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        (self.tmp / "prodotto.txt").write_text("output", encoding="utf-8")
        node, _ = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], node["artifacts"])

    def test_artifacts_non_dedotti_con_piu_nodi_rivendicati(self):
        """Con due nodi rivendicati insieme, la deduzione scatta solo se --artefatti è esplicito."""
        self.prepara_lavoro()
        # Rimuovi la dipendenza fra F02 e F01 in modo che F02 possa essere rivendicato in parallelo
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F02", blocked_by="F01")
        os.environ["ATLAS_IDENTITY"] = "esecutore-2"
        try:
            self.claims.claim(self.ref, "F02")
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)
        (self.tmp / "secondo-file.txt").write_text("output2", encoding="utf-8")
        node, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], node["artifacts"], "con piu' nodi in parallelo, artifacts deve restare vuoto")
        self.assertIsNotNone(avviso, "deve esserci un avviso sulla deduzione saltata")
        self.assertIn("--artefatti", avviso)

    def test_artifacts_deduzione_con_un_nodo_rivendicato(self):
        """Con un solo nodo rivendicato, la deduzione scatta regolarmente."""
        self.prepara_lavoro()
        node, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertIn("prodotto.txt", node["artifacts"], "la deduzione deve funzionare con un solo nodo")
        self.assertIsNone(avviso, "non deve esserci avviso quando la deduzione riesce")

    def test_artifacts_non_dedotti_nodo_aperto_mentre_altri_rivendicati(self):
        """Un nodo aperto che si chiude mentre un altro è rivendicato non deduce gli artefatti.

        Questo test cattura il buco: un nodo open (non rivendicato) si chiude, claimed(data)
        non lo include, e se ci sono altri nodi rivendicati la deduzione andrebbe comunque
        a pescare i file di quelli altri."""
        # Prepara il grafo con F01 e F02 indipendenti
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F02", blocked_by="F01")
        self.rispondi("F01")
        self.git_init()
        # Rivendica F02 da un altro agente (rimane rivendicato)
        os.environ["ATLAS_IDENTITY"] = "esecutore-2"
        try:
            self.claims.claim(self.ref, "F02")
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)
        # Scrivi un file (simulando il lavoro)
        (self.tmp / "prodotto.txt").write_text("output", encoding="utf-8")
        # Chiudi F01 senza rivendicarlo (rimane open), senza --artefatti
        node, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], node["artifacts"], "nodo aperto in parallelo con altri rivendicati non deduce")
        self.assertIsNotNone(avviso, "deve esserci avviso quando altri nodi sono rivendicati")
        self.assertIn("--artefatti", avviso)

    def test_i_markdown_generati_non_hanno_il_bom(self):
        """Ticket e mappa.md vanno scritti in UTF-8 puro, senza BOM."""
        self.popola()
        self.render_tutto()

        # Leggi in binario per verificare il BOM: in modalita' testo con utf-8-sig
        # il BOM verrebbe consumato in silenzio e il test non proverebbe niente.
        ticket_bytes = self.ref.ticket_path("F01").read_bytes()
        self.assertFalse(ticket_bytes.startswith(b"\xef\xbb\xbf"), "ticket ha il BOM UTF-8")

        map_bytes = self.ref.map_path.read_bytes()
        self.assertFalse(map_bytes.startswith(b"\xef\xbb\xbf"), "map.md ha il BOM UTF-8")

    def test_un_ticket_preesistente_con_bom_resta_allineabile(self):
        """Un ticket ereditato col BOM si riallinea e non perde la prosa scritta a mano.

        Non prova la scelta di utf-8-sig in lettura, che oggi non ha effetti osservabili:
        _coda() lavora con partition(), quindi il BOM cade nella testa scartata comunque.
        Tiene fermo il comportamento visibile, cioe' che il file esca riscritto e senza firma.
        """
        self.popola()
        data = self.store.load(self.ref.json_path)
        self.docs.write_stubs(self.ref, data)

        path = self.ref.ticket_path("F01")
        self.rispondi("F01")

        testo_originale = path.read_text(encoding="utf-8")
        path.write_bytes(b"\xef\xbb\xbf" + testo_originale.encode("utf-8"))

        # Modifica il nodo per forzare il riallineamento
        with self.mutate.editing(self.ref) as g:
            self.mutate.edit_node(g, "F01", title="Primo (modificato)")
        data = self.store.load(self.ref.json_path)

        self.docs.rewrite_heads(self.ref, data)

        testo_riscritto = path.read_text(encoding="utf-8")
        self.assertIn("Primo (modificato)", testo_riscritto)
        self.assertIn("La risposta.\n", testo_riscritto)

        bytes_riscritti = path.read_bytes()
        self.assertNotIn(b"\xef\xbb\xbf", bytes_riscritti)

    def test_claim_rigenera_la_dashboard_sotto_lock(self):
        """Il percorso comune di dispatch (claim, release, fog, render) rilegge e
        rigenera dentro read_transaction, non dopo una load a lock rilasciato.

        La prova e' strutturale di proposito: in un processo solo il lock non ha
        effetti osservabili sull'output, quindi la regressione della dashboard non
        si vede confrontando pagine. Quel che si puo' tenere fermo e' che il
        comando passi davvero dalla sezione critica, ed e' l'invariante di #14.
        """
        from core import cli, store
        self.popola()
        spia = mock.Mock(wraps=store.read_transaction)
        with mock.patch.object(cli, "read_transaction", spia):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, cli.main(["claim", "F01"]))
        spia.assert_called_once_with(self.ref.json_path)
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn("F01", html)

    def test_dashboard_non_regredisce_su_mutazioni_consecutive(self):
        """Verifica che read_transaction impedisce la regressione della dashboard
        quando due mutazioni avvengono in sequenza rapida.

        Il bug: claim() scrive graph.json, poi refresh() faceva load() fuori dal
        lock. Un secondo claim poteva scrivere graph.json nel frattempo, rendendo
        la dashboard stantia: mostra N1 claimed ma non N2.

        La correzione: read_transaction() rilegge sotto lock, quindi la dashboard
        contiene SEMPRE lo stato aggiornato.

        Il test simula: cattura lo stato dopo il primo claim, esegui il secondo claim
        (che modifica graph.json mentre il primo process sta per rigenerare), poi
        rigenerale con read_transaction e verifica che la dashboard sia corretta.
        """
        # Crea un grafo con due nodi paralleli (senza dipendenze)
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, id="N1", branch="A", title="Node 1", question="?")
            self.mutate.add_node(g, id="N2", branch="A", title="Node 2", question="?")

        # Primo claim: scrive N1 claimed in graph.json
        self.claims.claim(self.ref, "N1")
        dati_dopo_n1 = self.store.load(self.ref.json_path)

        # Verifica: N1 è claimed
        n1_claimed = [n for n in dati_dopo_n1["nodes"] if n["id"] == "N1"][0]
        self.assertEqual(self.store.CLAIMED, n1_claimed["status"])

        # Secondo claim: scrive N2 claimed in graph.json MENTRE il primo process
        # sta ancora rigenerando la dashboard (avrebbe letto i vecchi dati)
        self.claims.claim(self.ref, "N2", force=True)

        # Verifica: graph.json ora contiene ENTRAMBI i claim
        dati_veri = self.store.load(self.ref.json_path)
        n1_vera = [n for n in dati_veri["nodes"] if n["id"] == "N1"][0]
        n2_vera = [n for n in dati_veri["nodes"] if n["id"] == "N2"][0]
        self.assertEqual(self.store.CLAIMED, n1_vera["status"])
        self.assertEqual(self.store.CLAIMED, n2_vera["status"])

        # Simulazione del bug: il primo processo usa i dati OLD (dopo N1, prima N2)
        # e rigenerera la dashboard. Se usasse load() fuori dal lock, mostrerebbe
        # N1 claimed ma N2 ancora aperto.
        self.render.write(self.ref, dati_dopo_n1)  # usa OLD: N1 claimed, N2 aperto
        dash_stantia = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn('⬤ N1', dash_stantia, "Nella dashboard stantia, N1 è in lavorazione")
        self.assertNotIn('⬤ N2', dash_stantia, "Nella dashboard stantia, N2 è ancora aperto (non claimed)")

        # Con il fix: read_transaction rilegge sotto lock lo stato VERO
        with self.store.read_transaction(self.ref.json_path) as data:
            self.render.write(self.ref, data)  # rilegge stato VERO sotto lock

        # Verifica: la dashboard corretta contiene ENTRAMBI i claim
        dash_corretta = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn('⬤ N1', dash_corretta, "Dashboard corretta: N1 è in lavorazione")
        self.assertIn('⬤ N2', dash_corretta, "Dashboard corretta: N2 è in lavorazione (il fix chiude la finestra)")


class Doctor(Base):
    def test_doctor_regge_un_grafo_strutturalmente_rotto(self):
        """L'attrezzo di bordo non puo' essere il primo a rompersi: su un grafo con
        un arco verso un id inesistente deve stampare la diagnosi, non morire."""
        self.popola()
        dati = json.loads(self.ref.json_path.read_text(encoding="utf-8"))
        dati["nodes"][1]["blockedBy"] = ["FANTASMA"]
        self.ref.json_path.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.doctor.show_doctor(self.ws)          # non deve sollevare
        uscita = buffer.getvalue()
        self.assertIn("FANTASMA", uscita)
        self.assertIn("prova", uscita)                # nomina il grafo malato

    def test_fog_for_confine_di_parola(self):
        """fog_for deve usare confini di parola, non sottostringa: B1 ≠ B10."""
        self.popola()
        with self.store.transaction(self.ref.json_path) as data:
            data["fog"] = [
                "per B1: primo nodo",
                "per B10: decimo nodo",
                "B1 è menzionato qui nel testo",
                "B10 è menzionato qui nel testo",
            ]
        data = self.store.load(self.ref.json_path)
        risultati = self.model.fog_for(data, "B1")
        self.assertEqual(2, len(risultati))
        self.assertIn("per B1: primo nodo", risultati)
        self.assertIn("B1 è menzionato qui nel testo", risultati)
        self.assertNotIn("per B10: decimo nodo", risultati)
        self.assertNotIn("B10 è menzionato qui nel testo", risultati)

    def test_nessun_avviso_su_un_grafo_sano(self):
        self.popola()
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertEqual([], avvisi)

    def test_nodo_pendente_segnalato_se_non_e_lunico_cancello(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, id="F04", branch="F", title="Isolato", question="?")
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F04" in a for a in avvisi))

    def test_lucchetto_fermo_segnalato(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        with self.store.transaction(self.ref.json_path) as data:
            vecchio = (datetime.now().astimezone() - timedelta(hours=5)).isoformat(timespec="seconds")
            self.model.node_of(data, "F01")["claim"]["heartbeat"] = vecchio
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F01" in a for a in avvisi))

    def test_autoverifica_segnalata(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        _, _ = self.claims.close(self.ref, "F01", "fatto")
        self.claims.claim(self.ref, "F02")
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F02" in a and "F01" in a for a in avvisi))

    def test_scrittura_fuori_scopo_dopo_chiusura_segnalata(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        artefatto = self.ws.project_root / "prodotto.txt"
        artefatto.write_text("v1", encoding="utf-8")
        _, _ = self.claims.close(self.ref, "F01", "fatto", artifacts=["prodotto.txt"])
        with self.store.transaction(self.ref.json_path) as data:
            passato = (datetime.now().astimezone() - timedelta(hours=1)).isoformat(timespec="seconds")
            self.model.node_of(data, "F01")["closedAt"] = passato
        artefatto.write_text("v2 dopo la chiusura", encoding="utf-8")
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F01" in a and "prodotto.txt" in a for a in avvisi))

    def test_non_convergenza_avvisata_finche_il_grafo_vive(self):
        """L'avviso serve a scovare un ramo che non confluisce nel finale: a grafo
        finito non ha piu' niente da dire, e ripetuto insegna solo a ignorarlo."""
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F03", blocked_by="F02")   # due terminali: F02 (finale) e F03
        avvisi = self.doctor.doctor_avvisi(self.store.load(self.ref.json_path), self.ref, self.ws.config["agent"])
        self.assertTrue([a for a in avvisi if "F02" in a and "F03" in a])

        # chiudere il ramo sciolto non lo aggancia: finche' il grafo vive, resta segnalato
        self.rispondi("F03")
        self.claims.claim(self.ref, "F03")
        _, _ = self.claims.close(self.ref, "F03", "fatto")
        avvisi = self.doctor.doctor_avvisi(self.store.load(self.ref.json_path), self.ref, self.ws.config["agent"])
        self.assertTrue([a for a in avvisi if "F03" in a])

        for nodo_id in ("F01", "F02"):
            self.rispondi(nodo_id)
            self.claims.claim(self.ref, nodo_id)
            _, _ = self.claims.close(self.ref, nodo_id, "fatto")
        avvisi = self.doctor.doctor_avvisi(self.store.load(self.ref.json_path), self.ref, self.ws.config["agent"])
        self.assertFalse([a for a in avvisi if "F03" in a])

    def test_falso_positivo_sparisce_se_contenuto_non_cambia_in_git(self):
        """Quando la repo e' git, un file toccato ma non modificato nel contenuto
        (ad es. riscrittura identica o riallineamento mtime) non produce avviso.
        Questo test fallirebbe col vecchio criterio basato solo su mtime."""
        self.popola()
        self.git_init()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        artefatto = self.ws.project_root / "prodotto.txt"
        artefatto.write_text("v1", encoding="utf-8")
        # Fa un commit per registrare il file e portare HEAD avanti.
        subprocess.run(["git", "add", "."], cwd=self.tmp, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "artefatto"], cwd=self.tmp, check=True, capture_output=True)
        _, _ = self.claims.close(self.ref, "F01", "fatto", artifacts=["prodotto.txt"])
        # closedAt viene assegnato al momento della chiusura (adesso).
        # Aspetta un attimo per garantire che il prossimo evento sia dopo closedAt.
        import time
        time.sleep(0.05)
        # Tocca il file: riscrivilo con lo stesso contenuto.
        # Questo muove l'mtime ma git non vede cambio di contenuto.
        artefatto.write_text("v1", encoding="utf-8")
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        # L'avviso NOT deve esserci (il falso positivo sparisce).
        self.assertFalse(any("F01" in a and "prodotto.txt" in a for a in avvisi))

    def test_vero_positivo_resta_se_contenuto_cambia_in_git(self):
        """Quando il contenuto del file cambia davvero dopo la chiusura del nodo,
        anche in una repo git, l'avviso di doctor deve apparire."""
        self.popola()
        self.git_init()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        artefatto = self.ws.project_root / "prodotto.txt"
        artefatto.write_text("v1", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.tmp, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "artefatto"], cwd=self.tmp, check=True, capture_output=True)
        _, _ = self.claims.close(self.ref, "F01", "fatto", artifacts=["prodotto.txt"])
        # closedAt viene assegnato al momento della chiusura (adesso).
        # Aspetta un attimo per garantire che il prossimo evento sia dopo closedAt.
        import time
        time.sleep(0.05)
        # Cambia davvero il contenuto.
        artefatto.write_text("v2 dopo la chiusura", encoding="utf-8")
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        # L'avviso DEVE esserci (il vero positivo non scompare).
        self.assertTrue(any("F01" in a and "prodotto.txt" in a for a in avvisi))

    def test_show_status_con_nodo_rivendicato(self):
        """show_status deve stampare correttamente i nodi rivendicati con lo stato tradotto.
        Questo test scopre bug come la perdita di ETICHETTA durante i refactoring."""
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        data = self.store.load(self.ref.json_path)

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.report.show_status(self.ref, data)
        uscita = buffer.getvalue()

        # Verifica che la riga del nodo rivendicato sia presente e contenga:
        # - l'ID del nodo
        # - l'assignee (chi lo tiene, l'agente di default è "claude")
        # - la traduzione dello stato (dall'etichetta ETICHETTA["live"])
        self.assertIn("F01", uscita)
        self.assertIn("claude", uscita)  # l'agente di default che ha rivendicato
        self.assertIn("sessione viva", uscita)  # la traduzione dello stato 'live'


class PiuGrafi(Base):
    def test_grafi_isolati(self):
        self.popola()
        altro = self.mutate.create_graph(self.ws, "secondo", "Secondo", "Altra meta.")
        self.assertEqual(["prova", "secondo"], self.ws.slugs())
        self.assertEqual(0, len(self.store.load(altro.json_path)["nodes"]))
        self.assertNotEqual(self.ref.dashboard_path, altro.dashboard_path)

    def test_selezione_del_grafo_attivo(self):
        self.mutate.create_graph(self.ws, "secondo", "Secondo", "Altra meta.")
        with self.assertRaises(self.config.ConfigError):
            self.ws.graph()
        self.ws.pin("secondo")
        self.assertEqual("secondo", self.ws.graph().slug)
        os.environ["ATLAS_GRAPH"] = "prova"
        try:
            self.assertEqual("prova", self.ws.graph().slug)
        finally:
            os.environ.pop("ATLAS_GRAPH")
        self.assertEqual("prova", self.ws.graph("prova").slug)

    def test_slug_inesistente(self):
        with self.assertRaises(self.config.ConfigError):
            self.ws.graph("mai-esistito")


class PromozioneDallaNebbia(Base):
    """L'esempio installato in scripts/ viene eseguito davvero, non imitato: e' l'unico
    modo perche' il test si accorga se il template smette di girare."""

    def template(self, lingua: str) -> Path:
        return SORGENTE / "templates" / f"promote-fog.{lingua}.py.tmpl"

    def test_esegue_l_esempio_e_promuove_la_voce(self):
        self.popola()
        with self.store.transaction(self.ref.json_path) as data:
            data["fog"] = ["per F03: il primo dubbio", "un secondo dubbio, di nessuno"]

        script = self.root / "scripts" / "000-promote-fog.py"
        script.write_text(self.template("it").read_text(encoding="utf-8")
                          .replace("INDICE = None", "INDICE = 0")
                          .replace('"id": "X01"', '"id": "F04"')
                          .replace('"branch": "A"', '"branch": "F"'), encoding="utf-8")
        with self.mutate.editing(self.ref) as g:
            runpy.run_path(str(script))["run"](g)

        data = self.store.load(self.ref.json_path)
        self.assertEqual("Titolo del nodo nato dalla nebbia", self.model.node_of(data, "F04")["title"])
        self.assertEqual(["un secondo dubbio, di nessuno"], data["fog"])
        self.assertTrue([n for n in data["meta"]["notes"] if "F04" in n and "primo dubbio" in n])

    def test_l_esempio_si_rifiuta_finche_non_lo_compili(self):
        for lingua in ("it", "en"):
            with self.subTest(lingua=lingua):
                with self.assertRaises(NotImplementedError):
                    runpy.run_path(str(self.template(lingua)))["run"](None)


class TicketRiallineati(Base):
    """Il ticket è una vista, non una seconda verità: la sua testa discende dal grafo,
    e quel che ci si scrive sotto resta di chi l'ha scritto."""

    def lavorato(self, node_id: str = "F01") -> Path:
        """Un ticket con dentro del lavoro scritto a mano, come lo si trova in un progetto vero."""
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))
        path = self.ref.ticket_path(node_id)
        path.write_text(path.read_text(encoding="utf-8-sig") + "\nAppunti miei, da non perdere.\n",
                        encoding="utf-8-sig")
        return path

    def test_edit_node_si_riflette_nel_ticket(self):
        self.popola()
        path = self.lavorato("F02")
        with self.mutate.editing(self.ref) as g:
            self.mutate.edit_node(g, "F02", title="Titolo corretto", question="La domanda vera?")
            self.mutate.unlink(g, "F02", blocked_by="F01")
        self.assertEqual(1, self.docs.rewrite_heads(self.ref, self.store.load(self.ref.json_path)))
        testo = path.read_text(encoding="utf-8-sig")
        self.assertIn("Titolo corretto", testo)
        self.assertIn("La domanda vera?", testo)
        self.assertNotIn("Bloccato da: F01", testo)
        self.assertIn("Appunti miei, da non perdere.", testo)   # la prosa umana non si tocca

    def test_non_riscrive_se_non_e_cambiato_niente(self):
        self.popola()
        path = self.lavorato()
        prima = path.stat().st_mtime_ns
        self.assertEqual(0, self.docs.rewrite_heads(self.ref, self.store.load(self.ref.json_path)))
        self.assertEqual(prima, path.stat().st_mtime_ns)   # un mtime mosso a vuoto confonde doctor

    def test_migra_un_ticket_nato_prima_del_marker(self):
        self.popola()
        path = self.lavorato()
        vecchio = path.read_text(encoding="utf-8-sig")
        testa, _, coda = vecchio.partition(self.docs.MARK_END)
        path.write_text(testa.replace(self.docs.MARK, "") + coda, encoding="utf-8-sig")  # com'era prima
        self.assertEqual(1, self.docs.rewrite_heads(self.ref, self.store.load(self.ref.json_path)))
        testo = path.read_text(encoding="utf-8-sig")
        self.assertIn(self.docs.MARK_END, testo)
        self.assertIn("Appunti miei, da non perdere.", testo)

    def test_un_ticket_senza_confine_riconoscibile_si_segnala_e_non_si_tocca(self):
        self.popola()
        path = self.lavorato()
        path.write_text("Ho riscritto tutto a modo mio.\n", encoding="utf-8-sig")
        data = self.store.load(self.ref.json_path)
        self.assertEqual(["F01"], self.docs.unalignable(self.ref, data))
        self.assertEqual(0, self.docs.rewrite_heads(self.ref, data))
        self.assertEqual("Ho riscritto tutto a modo mio.\n", path.read_text(encoding="utf-8-sig"))
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue([a for a in avvisi if "F01" in a and self.docs.MARK_END in a])


class HowTo(Base):
    def stampa(self) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.howto.show(self.ws, "usage: atlas [-h] ...")
        return buffer.getvalue()

    def test_stampa_il_contratto_e_le_sei_sezioni(self):
        self.popola()
        uscita = self.stampa()
        self.assertIn("il grafo comanda il lavoro", uscita)     # dal contratto
        self.assertIn("usage: atlas", uscita)                    # l'help di argparse, passato da cli
        self.assertIn("mutate.add_node(g,", uscita)
        self.assertIn("atlas-work:", uscita)                     # le skill installate
        self.assertIn(".atlas/graphs/prova/tickets", uscita)     # i path, relativi al progetto
        for n in range(1, 7):
            self.assertIn(f"─── {n}.", uscita)

    def test_elenca_solo_le_mutazioni_da_script(self):
        nomi = [r.strip() for r in self.howto.mutazioni() if r.strip().startswith("mutate.")]
        self.assertTrue([n for n in nomi if n.startswith("mutate.add_node(")])
        for escluso in ("create_graph", "validate", "editing", "now"):
            self.assertFalse([n for n in nomi if n.startswith(f"mutate.{escluso}(")])

    def test_ogni_mutazione_ha_la_sua_voce_tradotta(self):
        """Il presidio della regola: una funzione nuova in mutate.py senza voce di
        catalogo esce dall'how-to muta, e questo test lo dice prima del rilascio."""
        for riga in self.howto.mutazioni():
            if not riga.strip().startswith("mutate."):
                continue
            nome = riga.strip()[len("mutate."):].split("(")[0]
            voce = self.strings.STRINGS.get(f"howto.mutate.{nome}")
            self.assertIsNotNone(voce, f"manca howto.mutate.{nome} nel catalogo")
            self.assertTrue(voce.get("it") and voce.get("en"), f"howto.mutate.{nome} non è tradotta")

    def test_in_inglese_stampa_il_contratto_inglese(self):
        (self.root / "config.json").write_text(json.dumps({"project": "prova", "language": "en"}), encoding="utf-8")
        self.strings.set_language("en")
        try:
            uscita = self.stampa()
            self.assertIn("the graph runs the work", uscita)
            self.assertIn("The commands", uscita)
        finally:
            self.strings.set_language("it")

    def test_regge_un_progetto_senza_grafi(self):
        vuoto = self.config.Workspace(self.root)
        (self.root / "graphs" / "prova").rename(self.root / "prova-messo-via")
        uscita = self.stampa()
        self.assertIn("nessun grafo ancora", uscita)
        self.assertEqual([], vuoto.slugs())


class Lingua(Base):
    def test_default_italiano_se_assente_dal_config(self):
        self.assertEqual("it", self.ws.config.get("language", "it"))
        self.assertEqual("chiuso", self.strings.t("state.closed"))

    def test_t_cambia_con_set_language(self):
        self.strings.set_language("en")
        self.assertEqual("closed", self.strings.t("state.closed"))
        self.strings.set_language("it")
        self.assertEqual("chiuso", self.strings.t("state.closed"))

    def test_t_ricade_su_it_per_lingua_sconosciuta(self):
        self.strings.set_language("fr")
        self.assertEqual("it", self.strings.current())

    def test_template_sceglie_lingua_semplice(self):
        (self.root / "config.json").write_text(json.dumps({"language": "en"}), encoding="utf-8")
        self.assertIn("## Question", self.ws.template("ticket.md"))
        (self.root / "config.json").write_text(json.dumps({"language": "it"}), encoding="utf-8")
        self.assertIn("## Domanda", self.ws.template("ticket.md"))

    def test_template_sceglie_lingua_estensione_composta(self):
        (self.root / "config.json").write_text(json.dumps({"language": "en"}), encoding="utf-8")
        self.assertIn("Run with:", self.ws.template("migration.py.tmpl"))


class Schema(Base):
    def test_schemaversion_uno_e_rilegibile(self):
        """Un grafo appena creato ha schemaVersion 1 e si rilegge senza errori."""
        data = self.store.load(self.ref.json_path)
        self.assertEqual(self.store.SCHEMA_VERSION, data["schemaVersion"])


if __name__ == "__main__":
    unittest.main()
