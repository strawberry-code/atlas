"""Test del motore: forma del grafo, lucchetti, artefatti derivati.

Ogni test lavora su una copia fresca di payload/ in una cartella temporanea, cosi'
prova esattamente il codice che finisce dentro un progetto ospite.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
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

    def _tabella(self, html: str) -> str:
        return html.split('<div class="tablewrap">')[1].split("</table>")[0]

    def test_dashboard_ha_la_vista_tabellare(self):
        self.popola()
        self.render_tutto()
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn('class="viewmode"', html)
        tabella = self._tabella(html)
        self.assertIn('class="gridtbl"', tabella)
        self.assertEqual(8, tabella.count("<th "))
        self.assertEqual(3, tabella.count("<tr data-node="))
        self.assertIn('<tr data-node="F01">', tabella)

    def test_tabella_regge_un_grafo_vuoto(self):
        self.render_tutto()
        self.assertIn('class="gridtbl"', self._tabella(self.ref.dashboard_path.read_text(encoding="utf-8")))

    def test_tabella_ordina_lo_stato_per_gravita_non_per_alfabeto(self):
        """frontier e' il primo in theme.ORDER: la cella di stato deve portare
        quell'indice come valore di ordinamento, non il testo dell'etichetta."""
        self.popola()
        self.render_tutto()
        tabella = self._tabella(self.ref.dashboard_path.read_text(encoding="utf-8"))
        riga_f01 = tabella.split('<tr data-node="F01">')[1].split("</tr>")[0]
        self.assertIn('data-v="0"', riga_f01)   # F01 e' in frontiera

    def test_tabella_mostra_ripieghi_per_dipendenze_costo_e_assegnazione(self):
        self.popola()
        self.render_tutto()
        tabella = self._tabella(self.ref.dashboard_path.read_text(encoding="utf-8"))
        riga_f01 = tabella.split('<tr data-node="F01">')[1].split("</tr>")[0]
        self.assertIn(self.strings.t("render.libero"), riga_f01)
        self.assertIn(self.strings.t("render.costo_ignoto"), riga_f01)
        self.assertIn(self.strings.t("render.tbl_non_assegnato"), riga_f01)
        riga_f02 = tabella.split('<tr data-node="F02">')[1].split("</tr>")[0]
        cella_dipendenze = riga_f02.rsplit("<td", 1)[1]
        self.assertIn(">F01<", cella_dipendenze)              # F02 e' bloccato da F01
        self.assertTrue(cella_dipendenze.startswith(' data-v="1"'),
                        "l'ordinamento e' per numero di bloccanti, non per l'id del bloccante")

    def test_tabella_mostra_chi_ha_cosa(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "marco", ["F01"])
        pagina = self.render.build(self.ref, self.store.load(self.ref.json_path))
        riga_f01 = self._tabella(pagina).split('<tr data-node="F01">')[1].split("</tr>")[0]
        self.assertIn(">marco<", riga_f01)

    def test_costo_numerico_estrae_solo_numeri_veri(self):
        casi = {"~40 chiamate": 40.0, "circa 1.5 ore": 1.5, "1,5 ore": 1.5,
                "15k token": 15.0, "Una sessione... .": None, "a occhio": None}
        for testo, atteso in casi.items():
            with self.subTest(testo=testo):
                self.assertEqual(self.render_panels.costo_numerico(testo), atteso)

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

    def sgancia(self, node_id: str, blocked_by: str):
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, node_id, blocked_by=blocked_by)

    def altra_sessione(self, azione):
        """Esegue azione() con un'altra identita', come farebbe un altro agente."""
        os.environ["ATLAS_IDENTITY"] = "esecutore-2"
        try:
            return azione()
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)

    def test_artifacts_non_dedotti_se_un_altro_nodo_chiude_dentro_la_finestra(self):
        """Il difetto di #19: l'altra sessione prende, lavora e chiude DENTRO la finestra.

        All'istante della chiusura di F01 c'e' un solo nodo rivendicato, quindi il
        controllo sincrono passa; ma i file dedotti da git includono anche quelli
        prodotti e gia' chiusi da F02."""
        self.prepara_lavoro()                       # claim di F01, poi un file scritto
        self.sgancia("F02", "F01")
        self.rispondi("F02")
        self.altra_sessione(lambda: self.claims.claim(self.ref, "F02"))
        (self.tmp / "roba-altrui.txt").write_text("output2", encoding="utf-8")
        self.altra_sessione(lambda: self.claims.close(self.ref, "F02", "fatto da un altro"))
        node, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], node["artifacts"], "il lavoro di F02 non va intestato a F01")
        self.assertIsNotNone(avviso, "la deduzione saltata va dichiarata")
        self.assertIn("F02", avviso, "l'avviso deve nominare il nodo che ha condiviso la finestra")

    def test_artifacts_dedotti_se_l_altra_chiusura_precede_la_presa(self):
        """Il caso sequenziale, che deve restare dedotto: chiudo F02, poi prendo F01."""
        self.popola()
        self.sgancia("F02", "F01")
        self.rispondi("F01")
        self.rispondi("F02")
        self.git_init()
        self.altra_sessione(lambda: self.claims.claim(self.ref, "F02"))
        self.altra_sessione(lambda: self.claims.close(self.ref, "F02", "fatto prima"))
        # I timestamp del grafo hanno la risoluzione del secondo: senza spostare
        # indietro la chiusura, in un test che gira in millisecondi la presa di F01
        # cadrebbe nello stesso secondo e il confronto direbbe 'finestra condivisa'
        # per un caso che condiviso non e'.
        with self.store.transaction(self.ref.json_path) as data:
            prima = datetime.now().astimezone() - timedelta(minutes=1)
            self.model.node_of(data, "F02")["closedAt"] = prima.isoformat(timespec="seconds")
        self.claims.claim(self.ref, "F01")
        (self.tmp / "prodotto.txt").write_text("output", encoding="utf-8")
        node, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertIn("prodotto.txt", node["artifacts"], "una chiusura precedente non sporca la finestra")
        self.assertIsNone(avviso)

    def test_artifacts_non_dedotti_se_un_altro_nodo_e_rilasciato_dentro_la_finestra(self):
        """Un rilascio motivato dentro la finestra vale come una chiusura: l'altra
        sessione ha lavorato, e i suoi file sono nel working tree."""
        self.prepara_lavoro()
        self.sgancia("F02", "F01")
        self.altra_sessione(lambda: self.claims.claim(self.ref, "F02"))
        self.altra_sessione(lambda: self.claims.release(self.ref, "F02", reason="cambio piano"))
        node, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], node["artifacts"])
        self.assertIn("F02", avviso)

    def test_artifacts_non_dedotti_con_istante_di_presa_illeggibile(self):
        """Un claim.at scritto a mano non deve far morire close, ne' dedurre alla cieca."""
        self.prepara_lavoro()
        with self.store.transaction(self.ref.json_path) as data:
            self.model.node_of(data, "F01")["claim"]["at"] = "ieri"
        node, avviso = self.claims.close(self.ref, "F01", "fatto", force=True)
        self.assertEqual([], node["artifacts"])
        self.assertIn("ieri", avviso)

    def test_close_stampa_i_file_dedotti(self):
        """Chi chiude vede subito cosa gli e' stato intestato, invece di scoprirlo
        rileggendo il grafo. Con --artefatti espliciti l'elenco non si ripete."""
        from core import cli
        self.prepara_lavoro()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["close", "F01", "-s", "fatto"]))
        uscita = buffer.getvalue()
        self.assertIn("prodotto.txt", uscita)
        self.assertIn("artefatti dedotti", uscita)

        self.rispondi("F02")
        self.claims.claim(self.ref, "F02")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["close", "F02", "-s", "fatto", "--artefatti", "mio.txt"]))
        self.assertNotIn("artefatti dedotti", buffer.getvalue())

    def test_amend_corregge_gli_artefatti_senza_toccare_la_chiusura(self):
        """Il caso di #20: la deduzione ha intestato file altrui, si riscrive la lista.

        closedAt e closedBy restano quelli veri, altrimenti il controllo di doctor
        sulle scritture postume misurerebbe dall'istante sbagliato."""
        self.prepara_lavoro()
        chiuso, _ = self.claims.close(self.ref, "F01", "la sintesi buona")
        with self.mutate.editing(self.ref) as g:
            self.mutate.amend(g, "F01", artifacts=["solo-mio.txt"])
        node = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual(["solo-mio.txt"], node["artifacts"])
        self.assertEqual(chiuso["closedAt"], node["closedAt"])
        self.assertEqual(chiuso["closedBy"], node["closedBy"])
        self.assertEqual("la sintesi buona", node["answer"], "la sintesi non passata resta")
        self.assertEqual(self.store.CLOSED, node["status"])
        self.assertEqual([["artifacts"]], [a["fields"] for a in node["amendments"]])

    def test_amend_registra_ogni_correzione_con_chi_e_quando(self):
        self.prepara_lavoro()
        self.claims.close(self.ref, "F01", "prima sintesi")
        with self.mutate.editing(self.ref) as g:
            self.mutate.amend(g, "F01", artifacts=["a.txt"])
        os.environ["ATLAS_IDENTITY"] = "chi-corregge"
        try:
            with self.mutate.editing(self.ref) as g:
                self.mutate.amend(g, "F01", cost="due ore", summary="sintesi corretta")
        finally:
            os.environ.pop("ATLAS_IDENTITY", None)
        node = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("sintesi corretta", node["answer"])
        self.assertEqual("due ore", node["cost"])
        self.assertEqual([["artifacts"], ["answer", "cost"]], [a["fields"] for a in node["amendments"]])
        self.assertEqual("chi-corregge", node["amendments"][-1]["by"])
        self.assertIsNotNone(self.model.istante(node["amendments"][-1]["at"]))

    def test_amend_rifiuta_un_nodo_non_chiuso(self):
        self.prepara_lavoro()
        with self.assertRaises(self.store.StateError) as caso:
            with self.mutate.editing(self.ref) as g:
                self.mutate.amend(g, "F01", artifacts=["a.txt"])
        self.assertIn("close", str(caso.exception), "l'errore deve dire dove si scrive la contabilità")

    def test_amend_senza_campi_rifiuta(self):
        self.prepara_lavoro()
        self.claims.close(self.ref, "F01", "fatto")
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.amend(g, "F01")

    def test_amend_dalla_cli(self):
        from core import cli
        self.prepara_lavoro()
        self.claims.close(self.ref, "F01", "fatto")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["amend", "F01", "--artefatti", "solo-mio.txt"]))
        self.assertIn("corretto", buffer.getvalue())
        node = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual(["solo-mio.txt"], node["artifacts"])

    def test_amend_svuota_il_campo_con_artefatti_senza_argomenti(self):
        """La stessa convenzione di close: --artefatti nudo dichiara 'nessuno'."""
        from core import cli
        self.prepara_lavoro()
        self.claims.close(self.ref, "F01", "fatto")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["amend", "F01", "--artefatti"]))
        node = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual([], node["artifacts"])

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
        # un nodo in lavorazione si riconosce dalla classe di stato: al posto del
        # glifo ⬤ la card porta l'anello che gira, che non e' testo
        in_lavorazione = 'class="n st-claimed" id="node-{}"'.format
        dash_stantia = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn(in_lavorazione("N1"), dash_stantia, "Nella dashboard stantia, N1 è in lavorazione")
        self.assertNotIn(in_lavorazione("N2"), dash_stantia,
                         "Nella dashboard stantia, N2 è ancora aperto (non claimed)")

        # Con il fix: read_transaction rilegge sotto lock lo stato VERO
        with self.store.read_transaction(self.ref.json_path) as data:
            self.render.write(self.ref, data)  # rilegge stato VERO sotto lock

        # Verifica: la dashboard corretta contiene ENTRAMBI i claim
        dash_corretta = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn(in_lavorazione("N1"), dash_corretta, "Dashboard corretta: N1 è in lavorazione")
        self.assertIn(in_lavorazione("N2"), dash_corretta,
                      "Dashboard corretta: N2 è in lavorazione (il fix chiude la finestra)")


class RipristinoChiusura(Base):
    """restore_closure riporta un nodo allo stato chiuso che la chiusura aveva su
    un'altra copia: i metadati passati sono quelli veri, e il nodo li ritrova
    identici, senza rifare nessuna delle verifiche che la chiusura aveva gia' fatto."""

    def test_ripristina_i_metadati_passati_non_l_ora_di_adesso(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.restore_closure(g, "F01", answer="fatto", closedBy="cristiano",
                                        closedAt="2026-01-02T03:04:05+01:00",
                                        cost="una mattinata", artifacts=["b.txt"])
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual(self.store.CLOSED, nodo["status"])
        self.assertEqual("fatto", nodo["answer"], "la risposta e' quella passata")
        self.assertEqual("cristiano", nodo["closedBy"], "closedBy e' quello passato")
        self.assertEqual("2026-01-02T03:04:05+01:00", nodo["closedAt"],
                         "closedAt e' il timestamp vecchio, identico, non l'ora di adesso")
        self.assertEqual("una mattinata", nodo["cost"], "il costo e' quello passato")
        self.assertEqual(["b.txt"], nodo["artifacts"], "gli artefatti sono quelli passati")

    def test_un_nodo_assegnato_resta_assegnato(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "marco", ["F01"])
        with self.mutate.editing(self.ref) as g:
            self.mutate.restore_closure(g, "F01", answer="fatto", closedBy="cristiano",
                                        closedAt="2026-01-02T03:04:05+01:00")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual(["marco"], nodo["owner"], "il vettore owner non si azzera")
        self.assertIsNone(nodo["assignee"], "assignee si azzera")
        self.assertIsNone(nodo["claim"], "claim si azzera")

    def test_campi_obbligatori_vuoti_rifiutati(self):
        self.popola()
        casi = [
            {"answer": "", "closedBy": "cristiano", "closedAt": "2026-01-02T03:04:05+01:00"},
            {"answer": "fatto", "closedBy": "   ", "closedAt": "2026-01-02T03:04:05+01:00"},
            {"answer": "fatto", "closedBy": "cristiano", "closedAt": None},
        ]
        for campi in casi:
            with self.subTest(campi=campi):
                with self.assertRaises(self.store.StateError):
                    with self.mutate.editing(self.ref) as g:
                        self.mutate.restore_closure(g, "F01", **campi)

    def test_un_nodo_gia_chiuso_o_fuori_scopo_rifiutato(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.claims.close(self.ref, "F01", "fatto")
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.restore_closure(g, "F01", answer="fatto", closedBy="cristiano",
                                            closedAt="2026-01-02T03:04:05+01:00")
        with self.mutate.editing(self.ref) as g:
            self.mutate.drop(g, "F02", "non serve piu'")
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.restore_closure(g, "F02", answer="fatto", closedBy="cristiano",
                                            closedAt="2026-01-02T03:04:05+01:00")

    def test_il_giro_completo_del_merge(self):
        """Chiusura vera, annotazione, reopen, ripristino: il nodo torna identico
        a com'era dopo la chiusura avvenuta sull'altra copia."""
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        chiuso, _ = self.claims.close(self.ref, "F01", "la sintesi buona",
                                      cost="due ore", artifacts=["a.py", "b.py"])
        with self.mutate.editing(self.ref) as g:
            self.mutate.reopen(g, "F01")
        with self.mutate.editing(self.ref) as g:
            self.mutate.restore_closure(g, "F01", chiuso["answer"], chiuso["closedBy"],
                                        chiuso["closedAt"], cost=chiuso["cost"],
                                        artifacts=chiuso["artifacts"])
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        for campo in ("status", "answer", "closedBy", "closedAt", "cost",
                      "artifacts", "owner", "assignee", "claim"):
            self.assertEqual(chiuso[campo], nodo[campo],
                             f"{campo} deve tornare com'era dopo la chiusura vera")


class Rinumerazione(Base):
    """La numerazione degli script di mutazione: compattare, spostare in coda,
    senza perdere un file per strada."""

    def scrivi(self, numero: int, nome: str, etichetta: str) -> Path:
        path = self.ws.scripts_dir / f"{numero:03d}-{nome}.py"
        path.write_text(f"# {etichetta}\n", encoding="utf-8")
        return path

    def test_compattazione_rinumera_chi_e_fuori_posto(self):
        from core import scripts
        self.scrivi(1, "a", "primo")
        self.scrivi(2, "b", "secondo")
        self.scrivi(2, "c", "terzo")
        self.scrivi(5, "d", "quarto")
        coppie = scripts.rinomine(self.ws.scripts_dir)
        self.assertEqual(
            [("002-c.py", "003-c.py"), ("005-d.py", "004-d.py")],
            [(da.name, a.name) for da, a in coppie],
            "la compattazione tocca solo chi e' fuori posto, nell'ordine di elenco")
        for da, a in coppie:
            da.rename(a)
        self.assertEqual(
            ["001-a.py", "002-b.py", "003-c.py", "004-d.py"],
            [p.name for p in scripts.elenco(self.ws.scripts_dir)],
            "i numeri diventano 001, 002, 003, 004 nell'ordine giusto")
        self.assertEqual("# terzo\n", (self.ws.scripts_dir / "003-c.py").read_text(encoding="utf-8"),
                         "il contenuto di 002-c segue il file in 003-c")
        self.assertEqual("# quarto\n", (self.ws.scripts_dir / "004-d.py").read_text(encoding="utf-8"),
                         "il contenuto di 005-d segue il file in 004-d")

    def test_sposta_in_coda_dopo_il_massimo_degli_altri(self):
        from core import scripts
        self.scrivi(1, "a", "primo")
        self.scrivi(2, "b", "secondo")
        self.scrivi(3, "c", "terzo")
        coppie = scripts.rinomine(self.ws.scripts_dir,
                                  [self.ws.scripts_dir / "002-b.py", self.ws.scripts_dir / "001-a.py"])
        self.assertEqual(
            [("002-b.py", "004-b.py"), ("001-a.py", "005-a.py")],
            [(da.name, a.name) for da, a in coppie],
            "i bersagli vanno in coda, nell'ordine indicato, dopo il massimo degli altri")
        for da, a in coppie:
            da.rename(a)
        self.assertEqual(
            ["003-c.py", "004-b.py", "005-a.py"],
            [p.name for p in scripts.elenco(self.ws.scripts_dir)],
            "gli altri restano al loro posto, i bersagli si accodano")

    def test_lo_scambio_di_due_numeri_non_perde_nessun_file(self):
        from core import cli
        self.scrivi(1, "a", "primo")
        self.scrivi(2, "a", "secondo")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["renumber", "002-a.py", "001-a.py"]))
        self.assertEqual("# secondo\n", (self.ws.scripts_dir / "001-a.py").read_text(encoding="utf-8"),
                         "002-a.py e' finito in 001-a.py senza sovrascrivere il vecchio")
        self.assertEqual("# primo\n", (self.ws.scripts_dir / "002-a.py").read_text(encoding="utf-8"),
                         "001-a.py e' finito in 002-a.py senza sovrascrivere il vecchio")

    def test_una_numerazione_gia_lineare_non_produce_rinomine(self):
        from core import scripts
        self.scrivi(1, "a", "primo")
        self.scrivi(2, "b", "secondo")
        self.scrivi(3, "c", "terzo")
        self.assertEqual([], scripts.rinomine(self.ws.scripts_dir),
                         "una numerazione gia' lineare non tocca niente")

    def test_un_bersaglio_inesistente_o_non_numerato_solleva(self):
        from core import scripts
        self.scrivi(1, "a", "primo")
        for bersaglio in (self.ws.scripts_dir / "999-manca.py", self.ws.scripts_dir / "nota.py"):
            with self.subTest(bersaglio=bersaglio.name):
                with self.assertRaises(self.store.StateError):
                    scripts.rinomine(self.ws.scripts_dir, [bersaglio])

    def test_prossimo_parte_da_uno_e_sale_col_massimo(self):
        from core import scripts
        self.assertEqual(1, scripts.prossimo(self.ws.scripts_dir), "cartella vuota → 1")
        self.scrivi(3, "a", "terzo")
        self.scrivi(7, "b", "settimo")
        self.assertEqual(8, scripts.prossimo(self.ws.scripts_dir), "il massimo piu' uno")

    def test_renumber_dry_run_non_tocca_il_disco(self):
        from core import cli
        self.scrivi(1, "a", "primo")
        self.scrivi(2, "b", "secondo")
        self.scrivi(2, "c", "terzo")
        self.scrivi(5, "d", "quarto")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["renumber", "--dry-run"]))
        self.assertIn("→", buffer.getvalue(), "il dry-run mostra le rinomine")
        self.assertEqual(
            ["001-a.py", "002-b.py", "002-c.py", "005-d.py"],
            sorted(p.name for p in self.ws.scripts_dir.iterdir()),
            "il dry-run non rinomina niente")

    def test_renumber_senza_argomenti_compatta(self):
        from core import cli
        self.scrivi(1, "a", "primo")
        self.scrivi(2, "b", "secondo")
        self.scrivi(2, "c", "terzo")
        self.scrivi(5, "d", "quarto")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["renumber"]))
        self.assertEqual(
            ["001-a.py", "002-b.py", "003-c.py", "004-d.py"],
            sorted(p.name for p in self.ws.scripts_dir.iterdir()),
            "la numerazione esce lineare")
        self.assertEqual("# terzo\n", (self.ws.scripts_dir / "003-c.py").read_text(encoding="utf-8"),
                         "il contenuto segue il file")

    def test_renumber_accetta_il_solo_nome_del_file(self):
        from core import cli
        self.scrivi(1, "a", "primo")
        self.scrivi(2, "b", "secondo")
        self.scrivi(3, "c", "terzo")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["renumber", "002-b.py"]))
        self.assertEqual(
            ["001-a.py", "003-c.py", "004-b.py"],
            [p.name for p in sorted(self.ws.scripts_dir.iterdir())],
            "il solo nome del file basta a spostarlo in coda")


class EsecuzioneScript(Base):
    """exec applica piu' script in una chiamata sola, ognuno nella propria
    transazione, fermandosi al primo che fallisce."""

    def scrivi_script(self, nome: str, corpo: str) -> Path:
        path = self.tmp / nome
        path.write_text(corpo, encoding="utf-8")
        return path

    def script_nodo(self, node_id: str) -> str:
        return ("from core import mutate\n"
                f"def run(g):\n"
                f"    mutate.add_node(g, id='{node_id}', branch='F', "
                f"title='Nodo {node_id}', question='?')\n")

    def test_due_script_arrivano_entrambi_nell_ordine_dato(self):
        from core import cli
        self.popola()
        primo = self.scrivi_script("primo.py", self.script_nodo("F04"))
        secondo = self.scrivi_script("secondo.py", self.script_nodo("F05"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["exec", str(primo), str(secondo)]))
        ids = [n["id"] for n in self.store.load(self.ref.json_path)["nodes"]]
        self.assertIn("F04", ids, "il primo script arriva nel grafo")
        self.assertIn("F05", ids, "il secondo script arriva nel grafo")
        self.assertLess(ids.index("F04"), ids.index("F05"),
                        "l'ordine di applicazione e' quello dato")

    def test_se_il_secondo_fallisce_il_primo_resta_e_il_terzo_non_parte(self):
        from core import cli
        self.popola()
        primo = self.scrivi_script("primo.py", self.script_nodo("F04"))
        secondo = self.scrivi_script("secondo.py", "def run(g):\n    raise RuntimeError('boom')\n")
        terzo = self.scrivi_script("terzo.py", self.script_nodo("F05"))
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(1, cli.main(["exec", str(primo), str(secondo), str(terzo)]))
        ids = [n["id"] for n in self.store.load(self.ref.json_path)["nodes"]]
        self.assertIn("F04", ids, "il primo script resta applicato")
        self.assertNotIn("F05", ids, "il terzo script non parte")
        self.assertIn("secondo.py", err.getvalue(), "l'errore nomina lo script caduto")

    def test_un_solo_script_continua_a_funzionare(self):
        from core import cli
        self.popola()
        solo = self.scrivi_script("solo.py", self.script_nodo("F04"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["exec", str(solo)]))
        ids = [n["id"] for n in self.store.load(self.ref.json_path)["nodes"]]
        self.assertIn("F04", ids, "lo script arriva nel grafo")


class Assegnazioni(Base):
    """L'assegnazione dice di chi e' il pezzo di lavoro; il claim dice chi ci ha le
    mani sopra adesso. Sono due campi diversi e non devono interferire."""

    def popola_due_rami(self):
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_branch(g, "F", "Fondamenta", "#4f46e5")
            self.mutate.add_branch(g, "B", "Backend", "#0ea5e9")
            self.mutate.add_node(g, id="F01", branch="F", title="Primo", question="?")
            self.mutate.add_node(g, id="F02", branch="F", title="Secondo", question="?")
            self.mutate.add_node(g, id="B01", branch="B", title="Backend uno", question="?")

    def owner(self, node_id: str):
        return self.model.owners_of(self.model.node_of(self.store.load(self.ref.json_path), node_id))

    def test_assegna_nodi_e_ramo(self):
        """Assegnare un ramo sovrascrive anche chi era gia' assegnato: e' un gesto
        esplicito su un insieme dichiarato, e la mezza assegnazione silenziosa
        lascerebbe un ramo per meta' di un altro senza dirlo a nessuno. Il comando
        stampa gli id che ha cambiato, quindi chi sovrascrive lo vede."""
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.assertEqual(["F01"], self.mutate.assign(g, "marco", ["F01"]))
            self.assertEqual(["F01", "F02"], self.mutate.assign(g, "lucia", branch="F"))
        self.assertEqual(["lucia"], self.owner("F01"))
        self.assertEqual(["lucia"], self.owner("F02"))
        self.assertEqual([], self.owner("B01"), "un altro ramo non viene toccato")

    def test_il_ramo_non_prende_i_nodi_aggiunti_dopo(self):
        """Espansione immediata: l'assegnatario sta sul nodo, non sul ramo."""
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "marco", branch="F")
            self.mutate.add_node(g, id="F03", branch="F", title="Terzo", question="?")
        self.assertEqual([], self.owner("F03"))

    def test_riassegnare_lo_stesso_nome_non_cambia_niente(self):
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "marco", ["F01"])
        with self.mutate.editing(self.ref) as g:
            self.assertEqual([], self.mutate.assign(g, "marco", ["F01"]))
            self.assertEqual([], self.mutate.unassign(g, ["F02"]), "F02 non era assegnato")
            self.assertEqual(["F01"], self.mutate.unassign(g, ["F01"]))
        self.assertEqual([], self.owner("F01"))

    def test_nomi_non_utilizzabili(self):
        self.popola_due_rami()
        for cattivo in ("", "   ", "a" * 41, "marco\x00rossi"):
            with self.subTest(nome=cattivo), self.assertRaises(self.store.StateError):
                with self.mutate.editing(self.ref) as g:
                    self.mutate.assign(g, cattivo, ["F01"])
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "  anna   maria \n", ["F01"])
        self.assertEqual(["anna maria"], self.owner("F01"), "spazi ripetuti e a capo collassano")

    def test_bersagli_inesistenti_si_fermano_prima_di_scrivere(self):
        self.popola_due_rami()
        for argomenti in ({"node_ids": ["MANCA"]}, {"branch": "Z"}, {}):
            with self.subTest(**argomenti), self.assertRaises(self.store.StateError):
                with self.mutate.editing(self.ref) as g:
                    self.mutate.assign(g, "marco", **argomenti)
        self.assertEqual([], self.owner("F01"), "nessuna scrittura parziale")

    def test_assegnare_non_invalida_la_presa_di_chi_lavora(self):
        """Il caso vero: si assegna un nodo mentre qualcuno lo sta lavorando.

        L'impronta registrata alla presa non deve cambiare, altrimenti chi chiude
        si sente dire che la premessa e' scaduta e deve passare da --force."""
        self.popola_due_rami()
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))
        self.claims.claim(self.ref, "F01")
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "lucia", ["F01"])
        path = self.ref.ticket_path("F01")
        path.write_text(path.read_text(encoding="utf-8").replace(
            "## Risposta", "## Risposta\n\nfatto"), encoding="utf-8")
        node, _ = self.claims.close(self.ref, "F01", "chiuso senza force")
        self.assertEqual("closed", node["status"])
        self.assertEqual(["lucia"], self.owner("F01"), "chiudere non cancella l'assegnazione")

    def test_edit_node_non_puo_riscrivere_l_assegnatario(self):
        self.popola_due_rami()
        with self.assertRaises(self.store.StateError):
            with self.mutate.editing(self.ref) as g:
                self.mutate.edit_node(g, "F01", owner="marco")

    def test_il_comando_assegna_e_whoami_fa_da_default(self):
        from core import cli
        self.popola_due_rami()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["assign", "marco", "F01", "B01"]))
            self.assertEqual(1, cli.main(["assign", "--me", "F02"]))   # nessun whoami ancora
            self.assertEqual(0, cli.main(["whoami", "giovanni"]))
            self.assertEqual(0, cli.main(["assign", "--me", "F02"]))
            self.assertEqual(0, cli.main(["unassign", "B01"]))
        self.assertEqual(["marco"], self.owner("F01"))
        self.assertEqual(["giovanni"], self.owner("F02"), "--me prende il nome da whoami")
        self.assertEqual([], self.owner("B01"))
        self.assertEqual("giovanni", self.ws.whoami())

    def test_whoami_si_legge_e_si_dimentica(self):
        from core import cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["whoami"]))
            self.assertEqual(0, cli.main(["whoami", "marco"]))
            self.assertEqual(0, cli.main(["whoami"]))
            self.assertEqual(0, cli.main(["whoami", "--clear"]))
            self.assertEqual(0, cli.main(["whoami"]))
        self.assertIsNone(self.ws.whoami())
        self.assertFalse(self.ws.whoami_file.exists())

    def test_la_dashboard_mostra_chi_ha_cosa(self):
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "marco", ["F01"])
            self.mutate.assign(g, "lucia", ["F02"])
        pagina = self.render.build(self.ref, self.store.load(self.ref.json_path))
        self.assertIn(">marco <b>1</b>", pagina)
        self.assertIn(">lucia <b>1</b>", pagina)
        self.assertIn('data-owner="0"', pagina, "il gruppo dei non assegnati esiste: B01")
        self.assertIn('body[data-owner="1"] .n:not([data-owners~="1"])', pagina)
        self.assertNotIn("marco", pagina.split("<style>")[1].split("</style>")[0],
                         "il nome non entra mai in un selettore CSS")

    def test_la_dashboard_tace_su_un_grafo_senza_assegnazioni(self):
        """Chi non usa questa parte non deve trovarsi controlli che non gli dicono niente."""
        self.popola_due_rami()
        pagina = self.render.build(self.ref, self.store.load(self.ref.json_path))
        self.assertNotIn("chip who", pagina)
        self.assertNotIn("body[data-owner=", pagina)

    def test_un_nome_ostile_non_esce_dalla_pagina(self):
        """Il nome lo scrive chiunque abbia la riga di comando e finisce in una pagina
        HTML: nel markup dev'essere testo, e nell'isola dati non deve poter chiudere
        il blocco script che la contiene. Con due persone l'unione dei nomi non deve
        aprire un buco in piu'."""
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, '</script><script>alert(1)</script>,anna', ["F01"])
        pagina = self.render.build(self.ref, self.store.load(self.ref.json_path))
        markup, resto = pagina.split('<script type="application/json" id="atlas-data">')
        isola, coda = resto.split("</script>", 1)
        self.assertNotIn("<script>alert(1)", markup)
        self.assertNotIn("<script>alert(1)", coda)
        self.assertIn("&lt;/script&gt;&lt;script&gt;", markup, "nel markup è testo, non tag")
        self.assertNotIn("</script", isola, "l'isola non si lascia chiudere dal dato")

    def test_persone_spezza_deduplica_e_ordina(self):
        """Il vettore dei nomi e' sempre distinto e in ordine, in qualunque ordine
        e ripetizione arrivino dalla riga di comando."""
        self.assertEqual(["anna", "marco"], self.mutate.persone("marco,anna"))
        self.assertEqual(["anna"], self.mutate.persone("anna,anna"))
        self.assertEqual(["anna"], self.mutate.persone("anna,"),
                         "la virgola di coda non e' un errore")
        self.assertEqual(["anna", "pedro"], self.mutate.persone("pedro,anna,pedro"))

    def test_persone_di_sole_virgole_solleva(self):
        """Senza nemmeno un nome non si puo' assegnare niente: e' un errore
        dichiarato, non un silenzio."""
        with self.assertRaises(self.store.StateError):
            self.mutate.persone(",,,")

    def test_nome_persona_rifiuta_virgola_e_piu(self):
        """Un nome solo non puo' contenere ne' la virgola ne' il '+': entrambi
        hanno un loro modo di spezzare, e ciascuno dice quale ha usato."""
        with self.assertRaises(self.store.StateError) as caso:
            self.mutate.nome_persona("anna,marco")
        self.assertIn("virgola", str(caso.exception))
        with self.assertRaises(self.store.StateError) as caso:
            self.mutate.nome_persona("cristiano+pedro")
        self.assertIn("persona sola", str(caso.exception))

    def test_assign_set_add_e_remove(self):
        """I tre modi: set sostituisce, add unisce senza duplicare, remove toglie
        solo i nomi indicati; ognuno torna solo i nodi davvero cambiati."""
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.assertEqual(["F01"], self.mutate.assign(g, "anna", ["F01"]))
            self.assertEqual([], self.mutate.assign(g, "anna", ["F01"]),
                             "assegnare due volte la stessa persona non cambia niente")
            self.assertEqual(["F01"], self.mutate.assign(g, "marco", ["F01"], modo="add"))
            self.assertEqual(["anna", "marco"], g.node("F01")["owner"])
            self.assertEqual([], self.mutate.assign(g, "marco", ["F01"], modo="add"),
                             "un nome gia' presente non duplica")
            self.assertEqual(["F01"], self.mutate.assign(g, "anna", ["F01"], modo="remove"))
            self.assertEqual(["marco"], g.node("F01")["owner"])
            self.assertEqual([], self.mutate.assign(g, "anna", ["F01"], modo="remove"),
                             "togliere un nome assente non cambia niente")

    def test_modo_sconosciuto_solleva(self):
        self.popola_due_rami()
        with self.assertRaises(self.store.StateError) as caso:
            with self.mutate.editing(self.ref) as g:
                self.mutate.assign(g, "anna", ["F01"], modo="sposta")
        self.assertIn("sposta", str(caso.exception))

    def test_il_vettore_sul_nodo_e_sempre_ordinato(self):
        """Anche chi passa i nomi in un ordine qualsiasi li ritrova scritti in
        ordine alfabetico, perche' il grafo versionato ha una sola forma."""
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "pedro,anna", ["F01"])
            self.assertEqual(["anna", "pedro"], g.node("F01")["owner"])

    def test_unassign_lascia_lista_vuota_non_none(self):
        """Un nodo libero e' un vettore vuoto, non una chiave assente: lo stesso
        stato non deve leggersi in due forme diverse nel JSON versionato."""
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "marco", ["F01"])
            self.assertEqual(["F01"], self.mutate.unassign(g, ["F01"]))
            self.assertEqual([], g.node("F01")["owner"])
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual([], nodo["owner"], "unassign scrive [], non None ne' toglie la chiave")

    def test_legge_un_grafo_vecchio_e_lo_mette_in_pari(self):
        """Il campo owner era una stringa: un grafo scritto prima del cambio si
        legge gia' come vettore, e la prima mutazione qualsiasi lo riscrive in
        forma nuova."""
        self.popola()
        dati = json.loads(self.ref.json_path.read_text(encoding="utf-8"))
        dati["nodes"][0]["owner"] = "cristiano"
        dati["nodes"][1]["owner"] = "cristiano+pedro"
        self.ref.json_path.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")

        data = self.store.load(self.ref.json_path)
        self.assertEqual(["cristiano"], self.model.owners_of(data["nodes"][0]))
        self.assertEqual(["cristiano", "pedro"], self.model.owners_of(data["nodes"][1]))

        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, id="F04", branch="F", title="Quarto", question="?")
        dati = json.loads(self.ref.json_path.read_text(encoding="utf-8"))
        self.assertEqual(["cristiano"], dati["nodes"][0]["owner"],
                         "dopo una mutazione il file porta la forma nuova")
        self.assertEqual(["cristiano", "pedro"], dati["nodes"][1]["owner"])

    def test_owners_elenca_i_nodi_di_ogni_persona_e_unowned_non_conta_i_condivisi(self):
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "anna,marco", ["F01"])
            self.mutate.assign(g, "marco", ["F02"])
        data = self.store.load(self.ref.json_path)
        self.assertEqual(["F01"], self.model.owners(data)["anna"],
                         "il nodo condiviso sta sotto tutte le sue persone")
        self.assertEqual(["F01", "F02"], self.model.owners(data)["marco"])
        self.assertEqual(["B01"], self.model.unowned(data),
                         "unowned non conta i nodi condivisi")

    def test_il_nodo_condiviso_nella_dashboard(self):
        """La resa di un nodo con piu' persone: gli indici nel SVG, i nomi nella
        tabella, la lista nel JSON della scheda."""
        self.popola_due_rami()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "anna,marco", ["F01"])
        pagina = self.render.build(self.ref, self.store.load(self.ref.json_path))

        self.assertIn('data-owners="1 2"', pagina, "il nodo condiviso porta piu' indici")

        tabella = pagina.split('<div class="tablewrap">')[1].split("</table>")[0]
        riga_f01 = tabella.split('<tr data-node="F01">')[1].split("</tr>")[0]
        self.assertIn(">anna, marco<", riga_f01, "la cella nomina entrambe le persone")

        isola = pagina.split('<script type="application/json" id="atlas-data">', 1)[1].split("</script>", 1)[0]
        dati = json.loads(isola.replace("<\\/", "</"))
        self.assertEqual(["anna", "marco"], dati["nodes"]["F01"]["owner"],
                         "il JSON della scheda porta una lista")


class ScegliereIlGrafo(Base):
    """Due persone davanti allo stesso schermo non sono riuscite a dare un render:
    scrivevano 'atlas piano render' o 'atlas render -g piano', e nessuna delle due
    funzionava. Il flag esiste da sempre, ma solo prima del sottocomando."""

    def test_il_flag_vale_anche_dopo_il_sottocomando(self):
        from core import cli
        parser = cli.build_parser()
        for argv in (["-g", "prova", "render"], ["render", "-g", "prova"],
                     ["-g", "prova", "status"], ["status", "-g", "prova"],
                     ["assign", "marco", "F01", "-g", "prova"]):
            with self.subTest(argv=argv):
                self.assertEqual("prova", parser.parse_args(argv).graph)
        self.assertIsNone(parser.parse_args(["render"]).graph,
                          "senza flag resta il grafo attivo, non una stringa vuota")

    def test_lo_slug_al_posto_del_comando_spiega_come_si_fa(self):
        from core import cli
        parser = cli.build_parser()
        errori = io.StringIO()
        with contextlib.redirect_stderr(errori), self.assertRaises(SystemExit):
            parser.parse_args([self.ref.slug, "render"])
        uscita = errori.getvalue()
        self.assertIn(f"-g {self.ref.slug}", uscita)
        self.assertIn(f"atlas use {self.ref.slug}", uscita)

    def test_un_refuso_non_riceve_il_consiglio_sbagliato(self):
        from core import cli
        parser = cli.build_parser()
        errori = io.StringIO()
        with contextlib.redirect_stderr(errori), self.assertRaises(SystemExit):
            parser.parse_args(["rendr"])
        self.assertNotIn("atlas use", errori.getvalue(), "'rendr' non è un grafo: niente consiglio")


class FigureDeiRami(Base):
    """Il ramo si legge da una figura in basso a destra, non piu' da una banda di
    colore sul bordo sinistro."""

    def popola_rami(self, quanti: int):
        with self.mutate.editing(self.ref) as g:
            for i in range(quanti):
                chiave = f"R{i}"
                self.mutate.add_branch(g, chiave, f"Ramo {i}", "#4f46e5")
                self.mutate.add_node(g, id=f"{chiave}01", branch=chiave, title=f"Nodo {i}", question="?")

    def test_ogni_ramo_ha_la_sua_figura_e_dopo_otto_si_ricomincia(self):
        from core import theme
        forme = [theme.shape_of(i) for i in range(len(theme.SHAPES))]
        self.assertEqual(len(set(forme)), len(forme), "due rami vicini avrebbero la stessa figura")
        self.assertEqual(theme.shape_of(0), theme.shape_of(len(theme.SHAPES)), "il nono ramo ricomincia")

    def test_ogni_figura_e_un_path_chiuso(self):
        from core import theme
        for nome, path in theme.SHAPES.items():
            with self.subTest(forma=nome):
                self.assertTrue(path.startswith("M"), f"{nome} non parte da un punto")
                self.assertTrue(path.rstrip().endswith("z"), f"{nome} non chiude il contorno")

    def test_la_dashboard_disegna_le_figure_e_non_piu_la_banda(self):
        self.popola_rami(3)
        pagina = self.render.build(self.ref, self.store.load(self.ref.json_path))
        self.assertNotIn('width="3" height="92"', pagina, "la banda del ramo è rimasta sulla card")
        self.assertEqual(3, pagina.count('class="bmark"'), "una figura per nodo")
        from core import theme
        for i in range(3):
            self.assertIn(theme.shape_of(i + 1), pagina)      # +1: il ramo A del grafo nuovo è il primo
        self.assertIn("branchShape", pagina, "la scheda del nodo non riceve la figura")


class Avanzamento(Base):
    """L'avanzamento conta i soli nodi chiusi, sul lavoro che resta da fare."""

    def prepara(self):
        self.popola()                       # F01, F02, F03 in catena
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, id="F04", branch="F", title="Quarto", question="?")
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.claims.close(self.ref, "F01", "fatto")

    def test_il_fuori_scopo_esce_da_tutti_e_due_i_termini(self):
        """Non e' lavoro fatto, ma non e' nemmeno lavoro che resta: pesare come
        debito eterno impedirebbe a un grafo vivo di arrivare al 100%."""
        self.prepara()
        self.assertEqual((1, 4), self.model.progress(self.store.load(self.ref.json_path)))
        with self.mutate.editing(self.ref) as g:
            self.mutate.drop(g, "F04", "non serve piu'")
        self.assertEqual((1, 3), self.model.progress(self.store.load(self.ref.json_path)))

    def test_prendere_un_nodo_non_fa_salire_l_avanzamento(self):
        """Il rivendicato resta al denominatore: e' lavoro aperto, e toglierlo
        premierebbe chi prende un nodo senza aver chiuso niente."""
        self.prepara()
        prima = self.model.progress(self.store.load(self.ref.json_path))
        self.claims.claim(self.ref, "F02")
        self.assertEqual(prima, self.model.progress(self.store.load(self.ref.json_path)))

    def test_un_grafo_con_nodi_fuori_scopo_arriva_al_cento_per_cento(self):
        self.prepara()
        with self.mutate.editing(self.ref) as g:
            self.mutate.drop(g, "F04", "fuori")
        for node_id in ("F02", "F03"):
            self.rispondi(node_id)
            self.claims.claim(self.ref, node_id)
            self.claims.close(self.ref, node_id, "fatto")
        fatti, totale = self.model.progress(self.store.load(self.ref.json_path))
        self.assertEqual(fatti, totale)


class FrecceColorate(Base):
    """Una freccia porta il colore dello stato del nodo da cui parte.

    E' la lettura che prima mancava: guardando le frecce che entrano in un blocco
    si sa in che stato sono le sue dipendenze senza doverle cercare sulla mappa, e
    tutte verdi vuol dire pronto."""

    def pagina(self) -> str:
        return self.render.build(self.ref, self.store.load(self.ref.json_path))

    def test_l_arco_prende_lo_stato_di_chi_lo_manda(self):
        self.popola()                                    # F01 → F02 → F03
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.claims.close(self.ref, "F01", "fatto")
        self.claims.claim(self.ref, "F02")
        pagina = self.pagina()
        self.assertIn('class="edge da-closed" data-from="F01" data-to="F02"', pagina)
        self.assertIn('class="edge da-claimed" data-from="F02" data-to="F03"', pagina)
        self.assertIn('class="port da-closed" data-from="F01"', pagina, "la porta segue l'arco")
        self.assertIn('marker-end="url(#tip-closed)"', pagina, "la punta segue la linea")

    def test_il_puntatore_ingrossa_l_arco_e_non_lo_ricolora(self):
        """L'evidenziazione dipingeva di verde gli entranti e di rosso gli uscenti:
        sopra un colore che porta lo stato del mittente, cancellava proprio quel che
        si era andati a guardare."""
        from core import render_edges
        css = render_edges.hover_css(["F01", "F02"])
        self.assertIn("stroke-width:2.6", css)
        self.assertNotIn("stroke:", css, "l'hover riscrive il colore dell'arco")
        self.assertNotIn("marker-end", css, "l'hover riscrive il colore della punta")

    def test_la_punta_segue_la_linea(self):
        """Un marker non eredita il colore del path: senza una punta per stato la
        freccia sarebbe colorata e la sua punta grigia."""
        from core import theme
        self.popola()
        pagina = self.pagina()
        css = (SORGENTE / "templates" / "dashboard.css").read_text(encoding="utf-8")
        for stato in theme.STATE:
            with self.subTest(stato=stato):
                self.assertIn(f'id="tip-{stato}"', pagina, "manca la punta di questo stato")
                self.assertIn(f".tip-{stato}{{fill:", css, "la punta non ha colore")


class TavolozzaScura(Base):
    """Il tema scuro sta scritto due volte, e le due copie devono coincidere.

    Una vale quando lo decide il sistema (media query), l'altra quando lo si sceglie
    col toggle: il CSS non permette di dichiararle una volta sola, e mentre si
    ritoccavano i colori una delle due e' rimasta indietro, dando alla stessa pagina
    due aspetti a seconda di come ci si era arrivati."""

    def tavole(self) -> tuple[dict, dict]:
        css = (SORGENTE / "templates" / "dashboard.css").read_text(encoding="utf-8")
        return self.token(css, ':root:not([data-theme="light"])'), self.token(css, ':root[data-theme="dark"]')

    @staticmethod
    def token(css: str, selettore: str) -> dict:
        inizio = css.index(selettore) + len(selettore)
        corpo = css[inizio: css.index("}", inizio)]
        return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", corpo))

    def test_le_due_tavole_scure_dicono_la_stessa_cosa(self):
        da_sistema, da_toggle = self.tavole()
        self.assertTrue(da_sistema, "la tavola della media query non è stata trovata")
        self.assertEqual(sorted(da_sistema), sorted(da_toggle), "le due tavole non hanno gli stessi token")
        for nome, valore in da_sistema.items():
            self.assertEqual(valore.strip(), da_toggle[nome].strip(), f"{nome} diverge fra le due tavole scure")


class Nebbia(Base):
    """Il caso di #21: 'fog --for X' anteponeva il prefisso anche a chi lo aveva gia'
    scritto nel testo, e in mappa restava per sempre 'per X: per X: ...'."""

    def test_il_prefisso_gia_scritto_non_viene_raddoppiato(self):
        casi = [
            ("per F02: il conto è incompleto", "per F02: il conto è incompleto", True),
            ("per F02 il conto è incompleto", "per F02: il conto è incompleto", True),
            ("  Per   F02  :  spazi e maiuscola", "per F02: spazi e maiuscola", True),
            ("il conto è incompleto", "per F02: il conto è incompleto", False),
        ]
        for scritto, atteso, ripetuto_atteso in casi:
            with self.subTest(scritto=scritto):
                riga, ripetuto = self.model.fog_line("F02", scritto)
                self.assertEqual(atteso, riga)
                self.assertEqual(ripetuto_atteso, ripetuto)

    def test_il_prefisso_di_un_altro_nodo_resta_nel_testo(self):
        """'per F03:' dentro una voce indirizzata a F02 e' contenuto, non un doppione."""
        riga, ripetuto = self.model.fog_line("F02", "per F03: parla di un altro")
        self.assertEqual("per F02: per F03: parla di un altro", riga)
        self.assertFalse(ripetuto)

    def test_il_confine_di_parola_vale_anche_nel_prefisso(self):
        """Come fog_for: con --for B1 una voce che dice 'per B10' non e' il prefisso di
        questo nodo. Senza confine la guardia mangiava lo zero e lasciava '0: ...'."""
        riga, ripetuto = self.model.fog_line("B1", "per B10: nodo diverso")
        self.assertEqual("per B1: per B10: nodo diverso", riga)
        self.assertFalse(ripetuto)

    def test_la_guardia_segue_la_lingua_del_progetto(self):
        self.strings.set_language("en")
        try:
            riga, ripetuto = self.model.fog_line("F02", "for F02: already prefixed")
            self.assertEqual("for F02: already prefixed", riga)
            self.assertTrue(ripetuto)
        finally:
            self.strings.set_language("it")

    def test_una_riga_di_solo_prefisso_resta_com_era(self):
        """Nessun testo residuo: e' una voce vuota, non un prefisso da normalizzare."""
        riga, ripetuto = self.model.fog_line("F02", "per F02:")
        self.assertEqual("per F02: per F02:", riga)
        self.assertFalse(ripetuto)

    def test_il_comando_scrive_una_riga_sola_e_lo_dice(self):
        from core import cli
        self.popola()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["fog", "per F02: il conto è incompleto", "--for", "F02"]))
        self.assertEqual(["per F02: il conto è incompleto"], self.store.load(self.ref.json_path)["fog"])
        self.assertIn("una volta sola", buffer.getvalue())

    def test_senza_destinatario_il_testo_resta_intatto(self):
        from core import cli
        self.popola()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["fog", "per F02: scritto a mano"]))
        self.assertEqual(["per F02: scritto a mano"], self.store.load(self.ref.json_path)["fog"])


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

    def test_owner_non_canonico_segnalato(self):
        """Un owner scritto a mano in forma vecchia ('cristiano+pedro') e' un grafo
        da mettere in pari: doctor lo segnala nominando il nodo, senza morire."""
        self.popola()
        dati = json.loads(self.ref.json_path.read_text(encoding="utf-8"))
        dati["nodes"][0]["owner"] = "cristiano+pedro"
        self.ref.json_path.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F01" in a and "cristiano" in a and "pedro" in a for a in avvisi),
                        "l'avviso nomina il nodo e legge l'assegnazione come vettore")

    def test_owner_in_forma_normale_tace(self):
        """Un grafo gia' in forma nuova non deve produrre l'avviso di forma."""
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.assign(g, "cristiano,pedro", ["F01"])
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertFalse(any("forma normale" in a for a in avvisi),
                         "nessun avviso sulla forma di un owner gia' normale")

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
        self.assertEqual([self.ref.slug, altro.slug], self.ws.slugs())
        self.assertEqual(0, len(self.store.load(altro.json_path)["nodes"]))
        self.assertNotEqual(self.ref.dashboard_path, altro.dashboard_path)

    def test_selezione_del_grafo_attivo(self):
        altro = self.mutate.create_graph(self.ws, "secondo", "Secondo", "Altra meta.")
        with self.assertRaises(self.config.ConfigError):
            self.ws.graph()
        self.ws.pin(altro.slug)
        self.assertEqual(altro.slug, self.ws.graph().slug)
        os.environ["ATLAS_GRAPH"] = self.ref.slug
        try:
            self.assertEqual(self.ref.slug, self.ws.graph().slug)
        finally:
            os.environ.pop("ATLAS_GRAPH")
        self.assertEqual(self.ref.slug, self.ws.graph(self.ref.slug).slug)

    def test_slug_inesistente(self):
        with self.assertRaises(self.config.ConfigError):
            self.ws.graph("mai-esistito")

    def test_ogni_grafo_nuovo_porta_la_data_di_creazione_nel_nome(self):
        """YYMMDD-<nome-tecnico>: il prefisso lo mette il motore, non chi chiama."""
        oggi = datetime.now().strftime("%y%m%d")
        self.assertEqual(f"{oggi}-prova", self.ref.slug)
        self.assertEqual(f"{oggi}-prova", self.store.load(self.ref.json_path)["meta"]["slug"])

    def test_il_nome_tecnico_si_normalizza_in_kebab_case(self):
        """Spazi, maiuscole e punteggiatura scritti a mano non devono finire nel
        nome di una cartella: solo lettere minuscole, cifre e trattini singoli."""
        strano = self.mutate.create_graph(self.ws, "  Nome Tecnico!! ", "Strano", "Verificare la normalizzazione.")
        oggi = datetime.now().strftime("%y%m%d")
        self.assertEqual(f"{oggi}-nome-tecnico", strano.slug)


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
        self.assertIn(f".atlas/graphs/{self.ref.slug}/tickets", uscita)  # i path, relativi al progetto
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
        (self.root / "graphs" / self.ref.slug).rename(self.root / "prova-messo-via")
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
