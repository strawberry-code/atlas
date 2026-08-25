"""Test della fusione a tre vie di graph.json per id di nodo.

Coprono gli scenari di research/A01-divergenza.md (S1-S9) tradotti in regole
di merge: chiusure disgiunte pulite, chiusura e claim concorrenti dichiarati,
array fusi per elemento (anche con cancellazioni), meta.updated = massimo,
ordine canonico per id, nodi presenti in un solo ramo, e tolleranza ai campi
nuovi (host/lease_until del ramo L). Il driver per git si prova su file veri.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SORGENTE = Path(__file__).resolve().parent.parent / "payload"


def nodo(nid: str, status: str = "open", **campi) -> dict:
    base = {"id": nid, "title": f"titolo {nid}", "branch": "A", "type": "task",
            "mode": "AFK", "status": status, "assignee": None, "owner": [],
            "blockedBy": [], "question": f"domanda {nid}", "answer": None,
            "claim": None, "artifacts": [], "createdAt": "2026-08-25T00:00:00+02:00"}
    base.update(campi)
    return base


def grafo(nodes: list, updated: str = "2026-08-25", **extra) -> dict:
    g = {"schemaVersion": 1,
         "meta": {"slug": "prova", "title": "Prova", "destination": "dest",
                  "updated": updated, "notes": []},
         "branches": {"A": {"label": "A", "color": "#000"}},
         "nodes": nodes, "fog": [], "outOfScope": []}
    g.update(extra)
    return g


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "payload"
        shutil.copytree(SORGENTE, self.root)
        sys.path.insert(0, str(self.root))
        for m in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[m]
        from core import merge
        self.merge = merge

    def tearDown(self):
        sys.path.remove(str(self.root))
        for m in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[m]
        shutil.rmtree(self.tmp)

    def fai(self, base: dict, ours: dict, theirs: dict):
        return self.merge.merge(base, ours, theirs)

    def nodo_fuso(self, graph: dict, nid: str) -> dict:
        return next(n for n in graph["nodes"] if n["id"] == nid)


class Chiusure(Base):
    def test_chiusure_disgiunte_si_fondono_pulite(self):
        b = grafo([nodo("X"), nodo("Y")])
        o = grafo([nodo("X", status="closed", answer="da noi", closedBy="M1",
                         closedAt="2026-08-25T10:00:00+02:00"), nodo("Y")])
        t = grafo([nodo("X"), nodo("Y", status="closed", answer="da loro", closedBy="M2",
                         closedAt="2026-08-25T11:00:00+02:00")])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual([], conflitti)
        self.assertEqual("closed", self.nodo_fuso(fuso, "X")["status"])
        self.assertEqual("da noi", self.nodo_fuso(fuso, "X")["answer"])
        self.assertEqual("closed", self.nodo_fuso(fuso, "Y")["status"])
        self.assertEqual("da loro", self.nodo_fuso(fuso, "Y")["answer"])

    def test_chiusura_stesso_nodo_conflitto_dichiarato(self):
        b = grafo([nodo("X")])
        o = grafo([nodo("X", status="closed", answer="A", closedBy="M1",
                         closedAt="2026-08-25T10:00:00+02:00")])
        t = grafo([nodo("X", status="closed", answer="B", closedBy="M2",
                         closedAt="2026-08-26T10:00:00+02:00")])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual(1, len(conflitti))
        self.assertEqual("X", conflitti[0]["node"])
        self.assertEqual("close", conflitti[0]["field"])
        x = self.nodo_fuso(fuso, "X")
        self.assertEqual("A", x["answer"])       # la chiusura intera di ours, non un miscuglio
        self.assertEqual("M1", x["closedBy"])
        self.assertEqual("2026-08-25T10:00:00+02:00", x["closedAt"])
        self.assertIn("conflicts", fuso)


class Array(Base):
    def test_blockedBy_si_fondono_per_elemento(self):
        b = grafo([nodo("X", blockedBy=["A"])])
        o = grafo([nodo("X", blockedBy=["A", "B"])])
        t = grafo([nodo("X", blockedBy=["A", "C"])])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual([], conflitti)
        self.assertEqual(["A", "B", "C"], self.nodo_fuso(fuso, "X")["blockedBy"])

    def test_una_cancellazione_confermata_non_viene_resuscitata(self):
        b = grafo([nodo("X", blockedBy=["A", "B"])])
        o = grafo([nodo("X", blockedBy=["A"])])        # B tolto da noi
        t = grafo([nodo("X", blockedBy=["A"])])        # B tolto anche da loro
        fuso, _ = self.fai(b, o, t)
        self.assertEqual(["A"], self.nodo_fuso(fuso, "X")["blockedBy"])

    def test_la_rimozione_di_un_solo_lato_vince(self):
        b = grafo([nodo("X", blockedBy=["A", "B"])])
        o = grafo([nodo("X", blockedBy=["A"])])        # noi togliamo B
        t = grafo([nodo("X", blockedBy=["A", "B"])])   # loro non lo toccano
        fuso, _ = self.fai(b, o, t)
        self.assertEqual(["A"], self.nodo_fuso(fuso, "X")["blockedBy"])


class Meta(Base):
    def test_meta_updated_e_il_massimo(self):
        b = grafo([nodo("X")], updated="2026-08-25")
        o = grafo([nodo("X")], updated="2026-08-25")
        t = grafo([nodo("X")], updated="2026-08-26")
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual([], conflitti)
        self.assertEqual("2026-08-26", fuso["meta"]["updated"])


class Ordine(Base):
    def test_ordine_canonico_per_id(self):
        o = grafo([nodo("B"), nodo("A")])              # inseriti in ordine inverso
        t = grafo([nodo("C")])
        fuso, _ = self.fai(grafo([]), o, t)
        self.assertEqual(["A", "B", "C"], [n["id"] for n in fuso["nodes"]])


class SoloUnLato(Base):
    def test_nodi_aggiunti_da_rami_diversi_coesistono(self):
        o = grafo([nodo("X")])
        t = grafo([nodo("Y")])
        fuso, conflitti = self.fai(grafo([]), o, t)
        self.assertEqual([], conflitti)
        self.assertEqual(["X", "Y"], [n["id"] for n in fuso["nodes"]])

    def test_una_parte_che_edita_e_l_altra_no_prende_l_edit(self):
        b = grafo([nodo("X")])
        o = grafo([nodo("X")])
        t = grafo([nodo("X", title="titolo nuovo")])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual([], conflitti)
        self.assertEqual("titolo nuovo", self.nodo_fuso(fuso, "X")["title"])


class CampiNuovi(Base):
    def test_host_e_lease_until_del_ramo_L_sopravvivono(self):
        claim = {"identity": "M1", "at": "2026-08-25T10:00:00+02:00"}
        b = grafo([nodo("X", status="claimed", assignee="claude", claim=claim)])
        o = grafo([nodo("X", status="claimed", assignee="claude",
                        claim={**claim, "host": "macchina-a", "lease_until": "2026-08-26T10:00:00+02:00"},
                        title="titolo nostro")])
        t = grafo([nodo("X", status="claimed", assignee="claude", claim=claim,
                        question="domanda loro")])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual([], conflitti)
        x = self.nodo_fuso(fuso, "X")
        self.assertEqual("macchina-a", x["claim"]["host"])
        self.assertEqual("2026-08-26T10:00:00+02:00", x["claim"]["lease_until"])
        self.assertEqual("titolo nostro", x["title"])
        self.assertEqual("domanda loro", x["question"])


class Claim(Base):
    def test_presa_concorrente_conflitto_dichiarato(self):
        b = grafo([nodo("X")])
        o = grafo([nodo("X", status="claimed", assignee="claude",
                        claim={"identity": "M1", "at": "2026-08-25T10:00:00+02:00"})])
        t = grafo([nodo("X", status="claimed", assignee="claude",
                        claim={"identity": "M2", "at": "2026-08-25T11:00:00+02:00"})])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual(1, len(conflitti))
        self.assertEqual("claim.identity", conflitti[0]["field"])
        self.assertEqual("M1", self.nodo_fuso(fuso, "X")["claim"]["identity"])


class StatoDivergente(Base):
    """La famiglia 'stato' di A01: le macchine portano lo stesso nodo su stati
    diversi (una chiude, l'altra prende; una rilascia, l'altra riprende). Nessuna
    regola dice quale valga: il merge lo dichiara e non lo risolve."""

    def test_chiusura_contro_presa_e_conflitto_dichiarato(self):
        b = grafo([nodo("X")])
        o = grafo([nodo("X", status="closed", answer="fatto", closedBy="M1",
                         closedAt="2026-08-25T10:00:00+02:00")])
        t = grafo([nodo("X", status="claimed", assignee="claude",
                        claim={"identity": "M2", "at": "2026-08-25T11:00:00+02:00"})])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual(1, len(conflitti))
        self.assertEqual("X", conflitti[0]["node"])
        self.assertEqual("status", conflitti[0]["field"])

    def test_rilascio_contro_ripristino_della_presa_e_conflitto_dichiarato(self):
        claim = {"identity": "M1", "at": "2026-08-25T10:00:00+02:00"}
        b = grafo([nodo("X", status="claimed", assignee="claude", claim=claim)])
        o = grafo([nodo("X", status="open", assignee=None, claim=None)])   # rilasciato da noi
        t = grafo([nodo("X", status="claimed", assignee="claude",
                        claim={"identity": "M2", "at": "2026-08-25T11:00:00+02:00"})])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual(1, len(conflitti))
        self.assertEqual("status", conflitti[0]["field"])


class CampoDescrittivo(Base):
    """A3 di A01: lo stesso campo descrittivo cambiato in modo diverso da
    entrambe le parti e' un disaccordo vero, da dichiarare e non da risolvere."""

    def test_ogni_campo_descrittivo_dichiarato_e_non_risolto(self):
        for campo in ("title", "question", "branch", "type", "mode"):
            with self.subTest(campo=campo):
                b = grafo([nodo("X", **{campo: "base"})])
                o = grafo([nodo("X", **{campo: "nostro"})])
                t = grafo([nodo("X", **{campo: "loro"})])
                fuso, conflitti = self.fai(b, o, t)
                self.assertEqual(1, len(conflitti))
                self.assertEqual("X", conflitti[0]["node"])
                self.assertEqual(campo, conflitti[0]["field"])
                self.assertEqual("value conflict", conflitti[0]["type"])
                # Non risolve: il fuso tiene il nostro, ma il conflitto resta dichiarato.
                self.assertEqual("nostro", self.nodo_fuso(fuso, "X")[campo])
                self.assertIn("conflicts", fuso)

    def test_una_parte_che_rimuove_e_l_altra_che_cambia_e_conflitto(self):
        b = grafo([nodo("X", title="T")])
        o = grafo([nodo("X", title="T nuovo")])
        t = grafo([nodo("X", title=None)])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual(1, len(conflitti))
        self.assertEqual("title", conflitti[0]["field"])


class RumoreClaim(Base):
    """B4 di A01: pid, session, at, heartbeat sono rumore locale del claim. Un
    claim con la stessa identita' ma battiti diversi non e' un conflitto: il
    nostro rumore vince in silenzio."""

    def test_il_rumore_locale_non_produce_conflitto(self):
        claim_b = {"identity": "M1", "pid": 1, "session": "s",
                   "at": "2026-08-25T10:00:00+02:00", "heartbeat": "2026-08-25T10:00:00+02:00"}
        b = grafo([nodo("X", status="claimed", assignee="claude", claim=claim_b)])
        claim_o = {**claim_b, "pid": 2, "session": "altra", "heartbeat": "2026-08-25T11:00:00+02:00"}
        claim_t = {**claim_b, "pid": 3, "session": "terza", "heartbeat": "2026-08-25T12:00:00+02:00"}
        o = grafo([nodo("X", status="claimed", assignee="claude", claim=claim_o)])
        t = grafo([nodo("X", status="claimed", assignee="claude", claim=claim_t)])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual([], conflitti)
        self.assertEqual("M1", self.nodo_fuso(fuso, "X")["claim"]["identity"])
        self.assertEqual(2, self.nodo_fuso(fuso, "X")["claim"]["pid"])


class Owner(Base):
    """B6 di A01: owner e' un campo derivato, si unisce e si rinormalizza
    invece di fare conflitto."""

    def test_owner_che_diverge_si_unisce_e_si_rinormalizza(self):
        b = grafo([nodo("X")])
        o = grafo([nodo("X", owner=["bob"])])
        t = grafo([nodo("X", owner=["anna"])])
        fuso, conflitti = self.fai(b, o, t)
        self.assertEqual([], conflitti)
        self.assertEqual(["anna", "bob"], self.nodo_fuso(fuso, "X")["owner"])


class Fog(Base):
    def test_set_merge_rispetta_le_cancellazioni(self):
        b = grafo([nodo("X")], fog=["a", "b"])
        o = grafo([nodo("X")], fog=["a"])
        t = grafo([nodo("X")], fog=["a"])
        fuso, _ = self.fai(b, o, t)
        self.assertEqual(["a"], fuso["fog"])

    def test_le_aggiunte_di_tutti_e_due_entrano(self):
        b = grafo([nodo("X")], fog=["a"])
        o = grafo([nodo("X")], fog=["a", "b"])
        t = grafo([nodo("X")], fog=["a", "c"])
        fuso, _ = self.fai(b, o, t)
        self.assertEqual(["a", "b", "c"], fuso["fog"])


class Driver(Base):
    def _scrivi(self, nome: str, graph: dict) -> str:
        path = self.tmp / nome
        path.write_text(json.dumps(graph), encoding="utf-8")
        return str(path)

    def test_pulito_scrive_il_risultato_e_esce_zero(self):
        b = self._scrivi("base", grafo([nodo("X")]))
        o = self._scrivi("ours", grafo([nodo("X", status="closed", answer="A", closedBy="M1",
                                                   closedAt="2026-08-25T10:00:00+02:00")]))
        t = self._scrivi("theirs", grafo([nodo("X")]))
        rc = self.merge.merge_files(b, o, t)
        self.assertEqual(0, rc)
        fuso = json.loads(Path(o).read_text(encoding="utf-8"))
        self.assertEqual("closed", next(n for n in fuso["nodes"] if n["id"] == "X")["status"])
        self.assertNotIn("conflicts", fuso)

    def test_conflitto_esce_uno_e_annota_nel_json(self):
        b = self._scrivi("base", grafo([nodo("X")]))
        o = self._scrivi("ours", grafo([nodo("X", status="closed", answer="A", closedBy="M1",
                                                   closedAt="2026-08-25T10:00:00+02:00")]))
        t = self._scrivi("theirs", grafo([nodo("X", status="closed", answer="B", closedBy="M2",
                                                     closedAt="2026-08-26T10:00:00+02:00")]))
        rc = self.merge.merge_files(b, o, t)
        self.assertEqual(1, rc)
        fuso = json.loads(Path(o).read_text(encoding="utf-8"))
        self.assertIn("conflicts", fuso)
        self.assertEqual("X", fuso["conflicts"][0]["node"])

    def test_il_file_di_un_ramo_che_manca_vale_vuoto(self):
        o = self._scrivi("ours", grafo([nodo("X")]))
        t = self._scrivi("theirs", grafo([nodo("Y")]))
        rc = self.merge.merge_files(str(self.tmp / "assente"), o, t)
        self.assertEqual(0, rc)
        fuso = json.loads(Path(o).read_text(encoding="utf-8"))
        self.assertEqual(["X", "Y"], [n["id"] for n in fuso["nodes"]])


class Cli(Base):
    def test_il_parser_accetta_merge_graph(self):
        from core import cli
        args = cli.build_parser().parse_args(["merge-graph", "base", "ours", "theirs"])
        self.assertEqual("merge-graph", args.cmd)
        self.assertEqual(("base", "ours", "theirs"), (args.base, args.ours, args.theirs))

    def test_dispatch_smista_al_driver(self):
        from core import cli
        args = cli.build_parser().parse_args(["merge-graph", "base", "ours", "theirs"])
        with mock.patch.object(self.merge, "merge_files", return_value=7) as chiamata:
            rc = cli.dispatch(None, args)
        self.assertEqual(7, rc)
        chiamata.assert_called_once_with("base", "ours", "theirs")

    def test_help_espone_i_placeholder_del_driver(self):
        import contextlib
        import io
        from core import cli
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit):
                cli.build_parser().parse_args(["merge-graph", "--help"])
        help_text = buf.getvalue()
        self.assertIn("%O", help_text)
        self.assertIn("%A", help_text)
        self.assertIn("%B", help_text)


if __name__ == "__main__":
    unittest.main()
