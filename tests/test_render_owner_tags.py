"""Issue #34: il tag dell'assegnatario sulla card, sulla scheda e nel
pannello assegnazioni deve portare la stessa tinta (render_owners.colore()),
e un nodo senza assegnatari deve mostrare 'Anonimo'/'Anonymous', mai niente.
Copre anche il ridisegno della card (Q0x): dimensioni nuove, riga di pillole
senza sovrapposizioni, anche quando gli assegnatari non ci stanno tutti.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import render_lite, render_owners, render_pills, render_sheet, render_svg  # noqa: E402
from core.strings import set_language, t  # noqa: E402


def _nodo(node_id: str, owner=(), *, mode="AFK", branch="b", title="Titolo", question="?",
          blocked_by=()) -> dict:
    return {"id": node_id, "title": title, "question": question, "branch": branch,
            "type": "task", "mode": mode, "owner": list(owner), "blockedBy": list(blocked_by),
            "status": "open"}


def _grafo(*nodi: dict) -> dict:
    return {"nodes": list(nodi), "branches": {"b": {"label": "Ramo B", "color": "#7d8da3"}},
            "meta": {"title": "Grafo di prova", "slug": "prova"}}


class Colore(unittest.TestCase):
    """render_owners.colore(): l'unica tavolozza, letta da chip/pannello/card/scheda."""

    def test_nessuno_non_ha_tinta(self):
        self.assertEqual("", render_owners.colore(render_owners.NESSUNO))

    def test_indici_diversi_tinte_diverse_entro_la_tavolozza(self):
        tinte = [render_owners.colore(i) for i in range(1, 9)]
        self.assertEqual(8, len(set(tinte)), "otto indici, otto tinte distinte")

    def test_oltre_la_tavolozza_gira_in_tondo(self):
        self.assertEqual(render_owners.colore(1), render_owners.colore(9))


class PillolaCard(unittest.TestCase):
    """render_pills.riga(): la riga in fondo alla card (assegnatari, modo, ramo)."""

    GEOM = dict(pad_in=16, w_card=260, pill_y=120, pill_h=20)

    def _rettangoli(self, svg: str) -> list[tuple[float, float]]:
        """(inizio, fine) di ogni pillola sulla riga, ordinati: usati per
        verificare che nessuna si sovrapponga alla successiva."""
        rect = [(float(m.group(1)), float(m.group(2)))
                for m in re.finditer(r'<rect x="([\d.]+)" y="120" width="([\d.]+)"', svg)]
        return sorted((x, x + w) for x, w in rect)

    def test_un_solo_assegnatario_pillola_piena_nella_tinta(self):
        node = _nodo("F01", ["cristiano"], mode="HITL")
        svg = render_pills.riga(node, 0, 0, tinta="#b45309", ramo_colore="#7d8da3",
                                ramo_indice=0, **self.GEOM)
        self.assertIn(">cristiano<", svg)
        self.assertIn('fill="#b45309"', svg)
        self.assertIn('class="npill-testo"', svg)

    def test_piu_assegnatari_una_pillola_a_testa_stessa_tinta(self):
        node = _nodo("F02", ["ana", "bruno"], mode="AFK")
        svg = render_pills.riga(node, 0, 0, tinta="#0f766e", ramo_colore="#7d8da3",
                                ramo_indice=0, **self.GEOM)
        self.assertIn(">ana<", svg)
        self.assertIn(">bruno<", svg)
        self.assertEqual(2, svg.count('fill="#0f766e"'))

    def test_nessun_assegnatario_pillola_anonima(self):
        node = _nodo("F03", [], mode="AFK")
        svg = render_pills.riga(node, 0, 0, tinta="", ramo_colore="#7d8da3",
                                ramo_indice=0, **self.GEOM)
        self.assertIn(f'>{t("render.anonimo")}<', svg)
        # 'Anonimo' e' a contorno come il badge del modo (npill-modo), mai
        # riempito nel colore di una persona (npill-testo, la classe delle
        # pillole assegnate: qui non deve comparire nessuna)
        self.assertNotIn('class="npill-testo"', svg)

    def test_elenco_lungo_si_accorcia_in_piu_n_senza_sovrapposizioni(self):
        node = _nodo("F04", ["alessandro", "benedetta", "costantino", "domenica",
                             "edoardo", "francesca"], mode="HITL")
        svg = render_pills.riga(node, 0, 0, tinta="#b45309", ramo_colore="#7d8da3",
                                ramo_indice=0, **self.GEOM)
        self.assertRegex(svg, r"\+\d")
        rettangoli = self._rettangoli(svg)
        for (_, fine), (inizio_succ, _) in zip(rettangoli, rettangoli[1:]):
            self.assertLessEqual(fine, inizio_succ, "due pillole si sovrappongono")
        # il badge del modo e la figura del ramo restano sempre presenti,
        # anche quando gli assegnatari si accorciano in '+N'
        self.assertIn(">HITL<", svg)
        self.assertIn('class="bmark"', svg)

    def test_pochi_assegnatari_restano_per_intero(self):
        node = _nodo("F05", ["ana", "bruno"], mode="AFK")
        svg = render_pills.riga(node, 0, 0, tinta="#0f766e", ramo_colore="#7d8da3",
                                ramo_indice=0, **self.GEOM)
        self.assertNotRegex(svg, r"\+\d", "due nomi corti ci stanno per intero")


class CardENuoveDimensioni(unittest.TestCase):
    """Q0x: la card e' piu' larga (260, da 230) e l'id sta in evidenza in cima."""

    def test_geometria(self):
        self.assertEqual(260, render_svg.W)
        self.assertGreater(render_svg.H, 134)

    def test_id_in_evidenza_e_titolo_restano_nella_card(self):
        data = _grafo(_nodo("Q01", ["cristiano"], title="Un titolo qualsiasi"))
        gruppi = render_owners.indice(data)
        svg = render_svg.boxes(data, {"Q01": (0, 0)}, {"Q01"}, gruppi)
        self.assertIn('class="nid"', svg)
        self.assertIn(">Q01<", svg)
        self.assertIn("Un titolo qualsiasi", svg)
        # niente footer testuale col vecchio formato 'modo · assegnatario · costo'
        self.assertNotIn('class="nfoot"', svg)


class ColoreCoerenteConIlPannello(unittest.TestCase):
    """La tinta della pillola sulla card/scheda e' la stessa che chip() e
    panel() disegnano per lo stesso insieme di assegnatari (issue #34): un
    solo calcolo, riusato in quattro punti."""

    def _grafo_due_persone(self) -> dict:
        return _grafo(
            _nodo("Q01", ["cristiano", "pedro"], mode="HITL"),
            _nodo("Q02", [], mode="AFK"),
        )

    def test_la_tinta_della_card_e_quella_del_pannello_coincidono(self):
        data = self._grafo_due_persone()
        gruppi = render_owners.indice(data)
        etichetta = "cristiano + pedro"
        tinta_attesa = render_owners.colore(gruppi[etichetta])
        self.assertTrue(tinta_attesa)

        pannello = render_owners.panel(data, gruppi)
        chip = render_owners.chips(data, gruppi)
        self.assertIn(f"background:{tinta_attesa}", pannello)
        self.assertIn(f"background:{tinta_attesa}", chip)

        svg = render_svg.boxes(data, {"Q01": (0, 0), "Q02": (300, 0)},
                               {"Q01", "Q02"}, gruppi)
        self.assertIn(f'fill="{tinta_attesa}"', svg)

    def test_la_scheda_riceve_la_stessa_tinta_nella_data_island(self):
        data = self._grafo_due_persone()
        gruppi = render_owners.indice(data)
        etichetta = "cristiano + pedro"
        tinta_attesa = render_owners.colore(gruppi[etichetta])

        class RefFinto:
            def ticket_path(self, node_id):
                return Path("/non-esiste")

        isola = render_sheet.data_island(RefFinto(), data, {"Q01", "Q02"}, gruppi)
        corpo = re.search(r'<script[^>]*>(.*)</script>', isola, re.S).group(1)
        # data_island() spezza '</' in '<\/' per non chiudere lo script in
        # anticipo: JSON valido, json.loads la rilegge da sola come '/'.
        payload = json.loads(corpo)
        self.assertEqual(tinta_attesa, payload["nodes"]["Q01"]["ownerColor"])
        self.assertEqual("", payload["nodes"]["Q02"]["ownerColor"], "senza assegnatari, nessuna tinta")


class PaginaAlleggerita(unittest.TestCase):
    """render_lite.py (S11/4, D02): niente legenda/pannello per persona, ma un
    nodo assegnato deve comunque portare la pillola nella sua tinta vera, non
    una pillola invisibile (testo bianco su niente) per un indice vuoto."""

    def test_pillola_assegnata_ha_una_tinta_vera_anche_senza_legenda(self):
        data = _grafo(_nodo("L01", ["cristiano"], mode="HITL"))
        html = render_lite.build(None, data)
        self.assertIn('class="npill-testo"', html)
        self.assertNotIn('fill=""', html, "una tinta vuota e' testo bianco su niente")


class SchedaAnonima(unittest.TestCase):
    """render_sheet.sheet(): il marcatore per la pillola 'Anonimo' e' nel
    markup, il vecchio prefisso 'assegnato a' (issue #34, orfano) no."""

    def test_attributo_anonimo_presente_prefisso_vecchio_assente(self):
        set_language("it")
        html = render_sheet.sheet()
        self.assertIn(f'data-anonimo="{t("render.anonimo")}"', html)
        self.assertNotIn("data-owner-label", html)

    def test_in_inglese_la_pillola_dice_anonymous(self):
        set_language("en")
        try:
            html = render_sheet.sheet()
            self.assertIn('data-anonimo="Anonymous"', html)
        finally:
            set_language("it")


if __name__ == "__main__":
    unittest.main()
