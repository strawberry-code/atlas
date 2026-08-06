"""Test del motore: forma del grafo, lucchetti, artefatti derivati.

Ogni test lavora su una copia fresca di payload/ in una cartella temporanea, cosi'
prova esattamente il codice che finisce dentro un progetto ospite.
"""
from __future__ import annotations

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
        from core import config, docs, mutate, render, store, model, claims, strings, report
        self.config, self.docs, self.mutate = config, docs, mutate
        self.render, self.store, self.model, self.claims = render, store, model, claims
        self.strings, self.report = strings, report
        self.ws = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo di prova", "Verificare il motore.")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
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
        self.assertEqual({"F01": 0, "F02": 1, "F03": 2}, self.model.levels(data))

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
        self.assertEqual({"F02", "F03"}, self.model.downstream(data, "F01"))

    def test_cammino_residuo_fino_al_terminale(self):
        data = self.popola()
        self.assertEqual(2, self.model.residual_path(data, "F01"))
        self.assertEqual(0, self.model.residual_path(data, "F03"))

    def test_ranked_frontier_ordina_per_impatto(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F02", blocked_by="F01")
        data = self.store.load(self.ref.json_path)
        ordinata = self.model.ranked_frontier(data)
        self.assertEqual(["F02", "F01"], [n["id"] for n, _, _ in ordinata])


class Lucchetti(Base):
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
        node = self.claims.close(self.ref, "F01", "sintesi")
        self.assertEqual("closed", node["status"])
        self.assertIn("closedAt", node)

    def test_close_registra_il_costo_se_dichiarato(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.rispondi("F01")
        node = self.claims.close(self.ref, "F01", "sintesi", cost="~40 chiamate")
        self.assertEqual("~40 chiamate", node["cost"])

    def test_close_registra_gli_artifacts_se_dichiarati(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.rispondi("F01")
        node = self.claims.close(self.ref, "F01", "sintesi", artifacts=["a.py", "b.py"])
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


class LucchettiWindows(Base):
    """claims.alive() sul ramo win32: os.kill(pid, 0) su Windows non e' un probe innocuo
    (per segnali diversi da CTRL_C/CTRL_BREAK la libc chiama TerminateProcess), quindi
    quel ramo deve passare da tasklist e non deve mai toccare os.kill."""

    def test_processo_vivo_non_chiama_mai_os_kill(self):
        with mock.patch("sys.platform", "win32"), \
             mock.patch("os.kill", side_effect=AssertionError("os.kill ucciderebbe il processo su Windows")), \
             mock.patch.object(self.claims, "subprocess") as sub:
            sub.run.return_value.stdout = '"claude.exe","4242","Console","1","10.000 K"\r\n'
            self.assertTrue(self.claims.alive(4242, "claude"))

    def test_processo_assente(self):
        with mock.patch("sys.platform", "win32"), \
             mock.patch.object(self.claims, "subprocess") as sub:
            sub.run.return_value.stdout = "INFO: No tasks are running which match the specified criteria.\r\n"
            self.assertFalse(self.claims.alive(4242, "claude"))


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
        self.claims.close(self.ref, "F01", "così si è deciso")
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
        self.popola()
        self.render_tutto()
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertNotIn("<script", html)
        self.assertNotIn("<link", html)
        self.assertIn('charset="utf-8"', html)
        self.assertEqual(3, html.count('class="card"'))
        for url in ("cdn", "googleapis", "unpkg"):
            self.assertNotIn(url, html)

    def test_dashboard_regge_un_grafo_vuoto(self):
        self.render_tutto()
        self.assertIn("<svg", self.ref.dashboard_path.read_text(encoding="utf-8"))

    def test_dashboard_mostra_il_costo_dichiarato(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.claims.close(self.ref, "F01", "fatto", cost="~40 chiamate")
        self.render_tutto()
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn("~40 chiamate", html)

    def prepara_lavoro(self):
        """Un nodo rivendicato in una repo git, con un file di lavoro appena scritto."""
        self.popola()
        self.rispondi("F01")
        self.git_init()
        self.claims.claim(self.ref, "F01")
        (self.tmp / "prodotto.txt").write_text("output", encoding="utf-8")

    def test_artifacts_dedotti_da_git_senza_flag(self):
        self.prepara_lavoro()
        node = self.claims.close(self.ref, "F01", "fatto")
        self.assertIn("prodotto.txt", node["artifacts"])
        self.assertFalse([p for p in node["artifacts"] if p.startswith(".atlas/")])

    def test_artifacts_espliciti_vincono_sulla_deduzione(self):
        self.prepara_lavoro()
        node = self.claims.close(self.ref, "F01", "fatto", artifacts=["esplicito.txt"])
        self.assertEqual(["esplicito.txt"], node["artifacts"])

    def test_artifacts_lista_vuota_svuota_il_campo(self):
        self.prepara_lavoro()
        node = self.claims.close(self.ref, "F01", "fatto", artifacts=[])
        self.assertEqual([], node["artifacts"])

    def test_artifacts_non_dedotti_fuori_da_una_repo_git(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        (self.tmp / "prodotto.txt").write_text("output", encoding="utf-8")
        node = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], node["artifacts"])


class Doctor(Base):
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
        avvisi = self.report.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertEqual([], avvisi)

    def test_nodo_pendente_segnalato_se_non_e_lunico_cancello(self):
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, id="F04", branch="F", title="Isolato", question="?")
        data = self.store.load(self.ref.json_path)
        avvisi = self.report.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F04" in a for a in avvisi))

    def test_lucchetto_fermo_segnalato(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        with self.store.transaction(self.ref.json_path) as data:
            vecchio = (datetime.now().astimezone() - timedelta(hours=5)).isoformat(timespec="seconds")
            self.model.node_of(data, "F01")["claim"]["heartbeat"] = vecchio
        data = self.store.load(self.ref.json_path)
        avvisi = self.report.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F01" in a for a in avvisi))

    def test_autoverifica_segnalata(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.claims.close(self.ref, "F01", "fatto")
        self.claims.claim(self.ref, "F02")
        data = self.store.load(self.ref.json_path)
        avvisi = self.report.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F02" in a and "F01" in a for a in avvisi))

    def test_scrittura_fuori_scopo_dopo_chiusura_segnalata(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        artefatto = self.ws.project_root / "prodotto.txt"
        artefatto.write_text("v1", encoding="utf-8")
        self.claims.close(self.ref, "F01", "fatto", artifacts=["prodotto.txt"])
        with self.store.transaction(self.ref.json_path) as data:
            passato = (datetime.now().astimezone() - timedelta(hours=1)).isoformat(timespec="seconds")
            self.model.node_of(data, "F01")["closedAt"] = passato
        artefatto.write_text("v2 dopo la chiusura", encoding="utf-8")
        data = self.store.load(self.ref.json_path)
        avvisi = self.report.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("F01" in a and "prodotto.txt" in a for a in avvisi))

    def test_nodi_pendenti_avvisati_finche_restano_aperti(self):
        """L'avviso serve a scovare un nodo dimenticato: a grafo finito non ha piu' niente
        da dire, e ripetuto a ogni esecuzione insegna solo a ignorarlo."""
        self.popola()
        with self.mutate.editing(self.ref) as g:
            self.mutate.unlink(g, "F03", blocked_by="F02")   # due foglie aperte: F02 e F03
        avvisi = self.report.doctor_avvisi(self.store.load(self.ref.json_path), self.ref, self.ws.config["agent"])
        self.assertTrue([a for a in avvisi if "F02" in a and "F03" in a])

        for nodo_id in ("F01", "F02", "F03"):
            self.rispondi(nodo_id)
            self.claims.claim(self.ref, nodo_id)
            self.claims.close(self.ref, nodo_id, "fatto")
        avvisi = self.report.doctor_avvisi(self.store.load(self.ref.json_path), self.ref, self.ws.config["agent"])
        self.assertFalse([a for a in avvisi if "F02" in a and "F03" in a])


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


if __name__ == "__main__":
    unittest.main()
