"""Lo stato 'suspended' e il registro di Lavorazione.

Un nodo sospeso e' un lavoro parziale congelato nel ticket: molla il lucchetto,
resta in frontiera, si riprende con take. Il registro (worklog.py) e' quel che
lo rende riprendibile: 'atlas log' scrive le voci chi/quando/cosa, 'suspend'
pretende che ce ne sia gia' una e ne aggiunge la propria, 'close' rifiuta un
ticket che non ne ha nessuna.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from tests.test_motore import Base  # noqa: E402

VOCE = re.compile(r"^- \*\*(?P<chi>[^*]+)\*\* · \d{4}-\d{2}-\d{2} \d{2}:\d{2}\n  (?P<cosa>.+)$", re.M)


class Registro(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def ticket(self, node_id="F01") -> str:
        return self.ref.ticket_path(node_id).read_text(encoding="utf-8")

    def test_il_ticket_nuovo_non_ha_voci(self):
        self.assertFalse(self.worklog.written(self.ref, "F01"))

    def test_log_scrive_chi_quando_cosa_nella_lavorazione(self):
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "luna"}):
            self.worklog.log(self.ref, "F01", "letto il lock\n\nscritto il test  ")
        testo = self.ticket()
        voci = VOCE.findall(testo)
        self.assertEqual([("luna", "letto il lock")], voci)
        self.assertIn("  scritto il test\n", testo, "le righe successive stanno rientrate sotto la prima")
        lavorazione = testo.partition("## Lavorazione")[2].partition("## Risposta")[0]
        self.assertIn("- **luna**", lavorazione, "la voce sta dentro la Lavorazione, non altrove")
        self.assertTrue(self.worklog.written(self.ref, "F01"))
        self.assertFalse(self.docs.answer_written(self.ref, "F01"), "la Risposta resta vuota")

    def test_log_appende_in_coda_e_rinfresca_il_battito(self):
        self.worklog.log(self.ref, "F01", "prima")
        with self.store.transaction(self.ref.json_path) as data:
            self.model.node_of(data, "F01")["claim"]["heartbeat"] = "2020-01-01T00:00:00+00:00"
        node = self.worklog.log(self.ref, "F01", "seconda")
        self.assertNotEqual("2020-01-01T00:00:00+00:00", node["claim"]["heartbeat"])
        cosa = [m.group("cosa") for m in VOCE.finditer(self.ticket())]
        self.assertEqual(["prima", "seconda"], cosa)

    def test_log_firma_con_l_agente_dentro_una_sessione_claude(self):
        with mock.patch.dict(os.environ, {"CLAUDE_PID": "4242"}, clear=False):
            os.environ.pop("ATLAS_IDENTITY", None)
            self.worklog.log(self.ref, "F01", "lavoro")
        self.assertEqual(["claude"], [m.group("chi") for m in VOCE.finditer(self.ticket())])

    def test_log_rifiuta_testo_vuoto_e_nodo_non_rivendicato(self):
        with self.assertRaises(self.store.StateError):
            self.worklog.log(self.ref, "F01", "   ")
        with self.assertRaises(self.store.StateError):
            self.worklog.log(self.ref, "F03", "lavoro")
        self.assertFalse(self.worklog.written(self.ref, "F01"))

    def test_log_senza_intestazione_dice_quale_file_aprire(self):
        path = self.ref.ticket_path("F01")
        path.write_text(path.read_text(encoding="utf-8").replace("## Lavorazione", "## Note"), encoding="utf-8")
        with self.assertRaises(self.store.StateError) as ctx:
            self.worklog.log(self.ref, "F01", "lavoro")
        self.assertIn("F01.md", str(ctx.exception))

    def test_close_rifiuta_senza_registro_e_force_scavalca(self):
        path = self.ref.ticket_path("F01")
        path.write_text(path.read_text(encoding="utf-8") + "\nLa risposta.\n", encoding="utf-8")
        with self.assertRaises(self.store.StateError) as ctx:
            self.claims.close(self.ref, "F01", "fatto", artifacts=[])
        self.assertIn("Lavorazione", str(ctx.exception))
        self.assertEqual("claimed", self.model.node_of(self.store.load(self.ref.json_path), "F01")["status"])
        node, _ = self.claims.close(self.ref, "F01", "fatto", force=True, artifacts=[])
        self.assertEqual("closed", node["status"])

    def test_close_passa_con_registro_e_risposta(self):
        self.worklog.log(self.ref, "F01", "lavoro")
        path = self.ref.ticket_path("F01")
        path.write_text(path.read_text(encoding="utf-8") + "\nLa risposta.\n", encoding="utf-8")
        node, _ = self.claims.close(self.ref, "F01", "fatto", artifacts=[])
        self.assertEqual("closed", node["status"])


class Sospensione(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def _node(self, node_id="F01"):
        return self.model.node_of(self.store.load(self.ref.json_path), node_id)

    def test_rifiuta_con_lavorazione_vuota_e_lascia_il_nodo_rivendicato(self):
        with self.assertRaises(self.store.StateError) as ctx:
            self.claims.suspend(self.ref, "F01", "manca il ramo Windows")
        self.assertIn("atlas log F01", str(ctx.exception))
        self.assertEqual("claimed", self._node()["status"])
        self.assertNotIn("suspensions", self.store.load(self.ref.json_path))

    def test_rifiuta_nota_vuota_e_nodo_non_rivendicato(self):
        self.worklog.log(self.ref, "F01", "lavoro")
        with self.assertRaises(self.store.StateError):
            self.claims.suspend(self.ref, "F01", "  ")
        with self.assertRaises(self.store.StateError):
            self.claims.suspend(self.ref, "F03", "nota")
        self.assertEqual("claimed", self._node()["status"])

    def test_congela_il_nodo_e_scrive_nota_e_voce(self):
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "luna"}):
            self.worklog.log(self.ref, "F01", "fatto il ramo POSIX")
            node = self.claims.suspend(self.ref, "F01", "manca il ramo Windows")
        self.assertEqual("suspended", node["status"])
        self.assertIsNone(node["claim"])
        self.assertIsNone(node["assignee"])
        data = self.store.load(self.ref.json_path)
        record = data["suspensions"][0]
        self.assertEqual(("F01", "manca il ramo Windows", "luna"), (record["id"], record["note"], record["by"]))
        voci = VOCE.findall(self.ref.ticket_path("F01").read_text(encoding="utf-8"))
        self.assertEqual([("luna", "fatto il ramo POSIX"), ("luna", "sospeso: manca il ramo Windows")], voci)

    def test_resta_in_frontiera_come_sospeso_e_si_riprende_con_take(self):
        self.worklog.log(self.ref, "F01", "lavoro")
        self.claims.suspend(self.ref, "F01", "nota")
        data = self.store.load(self.ref.json_path)
        self.assertEqual(["F01"], [n["id"] for n in self.model.frontier(data)])
        self.assertEqual(["F02", "F03"], [n["id"] for n in self.model.blocked(data)])
        from core import theme
        front = {n["id"] for n in self.model.frontier(data)}
        self.assertEqual("suspended", theme.state_of(self._node(), front))
        ripreso = self.claims.claim(self.ref, "F01")
        self.assertEqual("claimed", ripreso["status"])
        self.assertIsNotNone(ripreso["claim"]["fingerprint"])

    def test_avanzamento_conta_il_sospeso_come_lavoro_che_resta(self):
        self.worklog.log(self.ref, "F01", "lavoro")
        self.claims.suspend(self.ref, "F01", "nota")
        self.assertEqual((0, 3), self.model.progress(self.store.load(self.ref.json_path)))

    def test_la_mappa_e_il_brief_raccontano_la_sospensione(self):
        self.worklog.log(self.ref, "F01", "lavoro")
        self.claims.suspend(self.ref, "F01", "manca il ramo Windows")
        data = self.store.load(self.ref.json_path)
        self.assertIn("**F01** Primo sospeso: manca il ramo Windows", self.docs.decisions(data))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.report.show_brief(self.ref, data, "F01")
            self.report.show_status(self.ref, data)
        uscita = buffer.getvalue()
        self.assertIn("manca il ramo Windows", uscita)
        self.assertIn("sospeso, lavoro parziale nel ticket", uscita)

    def test_la_dashboard_marca_il_sospeso_in_frontiera(self):
        self.worklog.log(self.ref, "F01", "lavoro")
        self.claims.suspend(self.ref, "F01", "nota")
        data = self.store.load(self.ref.json_path)
        self.render.write(self.ref, data)
        html = self.ref.dashboard_path.read_text(encoding="utf-8")
        self.assertIn("st-suspended", html)
        self.assertIn('data-node="F01"><b>F01</b>', html)
        self.assertRegex(html, r'data-node="F01">.*?chip-state warn[^>]*><i class="chip-state-dot"></i>sospeso')

    def test_doctor_segnala_un_sospeso_senza_registro(self):
        self.worklog.log(self.ref, "F01", "lavoro")
        self.claims.suspend(self.ref, "F01", "nota")
        path = self.ref.ticket_path("F01")
        path.write_text(self.ws.template("ticket.md").replace("{id}", "F01"), encoding="utf-8")
        avvisi = self.doctor.doctor_avvisi(self.store.load(self.ref.json_path), self.ref,
                                           self.ws.config["agent"])
        self.assertTrue(any("F01" in a and "Lavorazione" in a for a in avvisi), avvisi)

    def test_lo_stato_e_del_motore_non_del_vocabolario_di_progetto(self):
        """Un config.json scritto prima della 0.20 elenca gli stati senza 'suspended':
        la validazione non deve leggerlo, o ogni sospensione morirebbe alla mutazione dopo."""
        cfg = self.root / "config.json"
        cfg.write_text('{"project": "prova", "vocab": {"statuses": ["open", "claimed", "closed", "out-of-scope"]}}',
                       encoding="utf-8")
        self.worklog.log(self.ref, "F01", "lavoro")
        self.claims.suspend(self.ref, "F01", "nota")
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, id="F04", branch="F", title="Quarto", question="?")
        self.assertEqual("suspended", self._node()["status"])
        with self.assertRaises(self.store.StateError):
            with self.store.transaction(self.ref.json_path) as data:
                self.model.node_of(data, "F04")["status"] = "wip"
            with self.mutate.editing(self.ref):
                pass


class SospensioneCLI(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def _run(self, *argv):
        from core import cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            codice = cli.main(list(argv))
        return codice, buffer.getvalue()

    def test_log_poi_suspend_poi_take(self):
        codice, uscita = self._run("log", "F01", "letto il codice", "--identity", "luna")
        self.assertEqual(0, codice, uscita)
        self.assertIn("F01.md", uscita)
        codice, uscita = self._run("suspend", "F01", "-m", "manca il ramo Windows")
        self.assertEqual(0, codice, uscita)
        self.assertIn("F01 sospeso", uscita)
        codice, uscita = self._run("take", "F01")
        self.assertEqual(0, codice, uscita)
        self.assertIn("manca il ramo Windows", uscita, "take stampa la nota di sospensione")

    def test_suspend_senza_registro_esce_con_errore(self):
        codice, uscita = self._run("suspend", "F01", "-m", "nota")
        self.assertEqual(1, codice)
        self.assertIn("atlas log F01", uscita)


if __name__ == "__main__":
    import unittest
    unittest.main()
