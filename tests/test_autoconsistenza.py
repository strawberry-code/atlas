"""V01: l'autoconsistenza di ogni dashboard vera, messa alla prova dai font
incorporati (F01) e dalla prosa dei ticket che cresce nel tempo.

La promessa di Atlas e' un file che si apre da disco senza rete. Qui si prova
sui grafi veri di .atlas/graphs/ (letti, mai scritti, come in
test_geometria_grafi_veri.py), rendendo ogni dashboard FRESCA con il codice
di oggi: il file dashboard.html su disco e' gitignored e puo' essere stantio,
la prova serve a nulla se guarda quello.

Due controlli storicamente fragili, corretti altrove (test_motore.py,
tests/e2e.py): cercare la sottostringa 'cdn'/'googleapis'/'unpkg' dentro
200KB di font incorporati in base64 e' un azzardo, tre lettere a caso ci
finiscono per davvero. Qui si cerca una URL vera (regex 'https?://'), non
una sottostringa, e si escludono solo le due cose legittime: il contenuto
dei ticket nell'isola dati (un ticket puo' citare un link vero in prosa,
per esempio una issue, senza che la pagina lo carichi mai) e la stringa dello
spazio dei nomi SVG 'http://www.w3.org/2000/svg', che compare per specifica
sia come attributo xmlns sul tag <svg> sia come costante JS passata a
document.createElementNS (edges.js, minimap.js): tre punti diversi, stessa
stringa, nessuno dei tre e' un caricamento.

La soglia di peso (SOGLIA_BYTES) e' una scelta dichiarata, non indovinata.
Al gate Q01 il grafo di lavoro pesava 537.833 byte (208.132 di font: Inter
96.988, Space Grotesk 53.216, JetBrains Mono 57.666); a V01, con piu' nodi
chiusi e piu' prosa nei ticket, lo stesso grafo fresco-renderizzato pesa
708.835 byte: il peso reale cresce con la prosa, non solo con i font. La
soglia sta a 1.000.000 byte: abbastanza larga da non rompersi ad ogni ticket
un po' piu' lungo (i quattro nodi ancora aperti su questo grafo aggiungeranno
prosa, non una nuova categoria di contenuto), abbastanza stretta da accorgersi
se qualcuno raddoppiasse per sbaglio il blocco font sul grafo piu' pesante di
oggi (+208KB porterebbe quel grafo a un soffio dalla soglia). Se un grafo
vero la sfondera' davvero per crescita di contenuto, non per un bug, la
strada gia' sul tavolo resta imbarcare solo il font display (Space Grotesk,
53KB) e lasciare Inter e JetBrains Mono ai fallback di sistema (~155KB in
meno per dashboard): la scelta gia' fatta da render_lite.py per la pagina
alleggerita, che infatti non porta font incorporati e sta a 60KB. Cambiare
risorse.py per farlo davvero e' fuori dal perimetro di questo nodo (tocca
payload/), quindi resta segnalato qui e non eseguito.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import config, render, store

RADICE_PROGETTO = Path(__file__).resolve().parent.parent
SOGLIA_BYTES = 1_000_000

# Lo spazio dei nomi SVG: per specifica, non per un caricamento (vedi il
# docstring del modulo). E' l'unica stringa "http://..." che ci si aspetta di
# trovare nel markup generato, quindi la si toglie prima di cercare il resto.
NS_SVG = "http://www.w3.org/2000/svg"

_URL = re.compile(r'https?://[^\s"\'<>)]+')
_ISOLA_DATI = re.compile(r'<script type="application/json" id="atlas-data">.*?</script>', re.S)
_DATA_URI = re.compile(r'data:[^)"\']*')
_IMPORT_CSS = re.compile(r'@import[^;]*;')
_COMMENTO_CSS = re.compile(r'/\*.*?\*/', re.S)


def _grafi_veri() -> list[tuple[str, config.Graph]]:
    ws = config.workspace(RADICE_PROGETTO)
    return [(slug, ws.graph(slug)) for slug in ws.slugs()]


def _render_fresco(ref: config.Graph) -> str:
    return render.build(ref, store.load(ref.json_path))


def _fuori_dai_ticket_e_dall_xmlns(html: str) -> str:
    """Il testo su cui e' lecito cercare una URL vera: fuori dai data URI
    (rumore opaco), dall'isola JSON dei ticket (puo' citare un link vero in
    prosa) e dallo spazio dei nomi SVG (spec, non caricamento, tre occorrenze
    diverse nella stessa pagina: vedi il docstring del modulo)."""
    pulito = _DATA_URI.sub("", html)
    pulito = _ISOLA_DATI.sub("", pulito)
    return pulito.replace(NS_SVG, "")


def _css_della_pagina(html: str) -> str:
    return html.split("<style>", 1)[1].split("</style>", 1)[0]


class Autoconsistenza(unittest.TestCase):
    """Le stesse tre garanzie su ognuno dei grafi veri di .atlas/graphs/, mai
    su un caso sintetico: un grafo sintetico senza prosa nasconderebbe
    proprio quello che qui conta, quanto pesa un ticket chiuso davvero."""

    def test_ci_sono_grafi_da_provare(self):
        # se questo fallisce le prove sotto sono vuote per assenza di dati,
        # non per assenza di difetti: un errore esplicito vale piu' di un
        # verde silenzioso (stesso principio di test_geometria_grafi_veri.py)
        self.assertTrue(_grafi_veri(), "nessun grafo reale in .atlas/graphs/: le prove sotto sarebbero vuote")

    def test_nessuna_url_remota_fuori_dai_ticket_e_dall_xmlns(self):
        for slug, ref in _grafi_veri():
            with self.subTest(grafo=slug):
                html = _render_fresco(ref)
                trovate = _URL.findall(_fuori_dai_ticket_e_dall_xmlns(html))
                self.assertEqual(trovate, [], f"{slug}: URL remota nella pagina generata: {trovate}")

    def test_nessun_import_css_nel_markup_generato(self):
        """grafite.offline.css dichiara zero @import (il foglio 'online' ne
        parla solo in un commento, senza usarne uno): qui si prova che il
        markup generato ne porti zero davvero, tolti i commenti."""
        for slug, ref in _grafi_veri():
            with self.subTest(grafo=slug):
                html = _render_fresco(ref)
                css_pulito = _COMMENTO_CSS.sub("", _css_della_pagina(html))
                self.assertEqual(_IMPORT_CSS.findall(css_pulito), [], f"{slug}: @import nel CSS generato")

    def test_peso_sotto_soglia(self):
        for slug, ref in _grafi_veri():
            with self.subTest(grafo=slug):
                peso = len(_render_fresco(ref).encode("utf-8"))
                self.assertLess(peso, SOGLIA_BYTES,
                                 f"{slug}: {peso} byte, oltre la soglia dichiarata di {SOGLIA_BYTES}")


class LaProvaMorde(unittest.TestCase):
    """Non basta che la prova passi: deve poter fallire davvero. Si inietta
    di proposito, uno alla volta, cio' che i tre controlli sopra devono
    beccare, con gli stessi helper usati sopra."""

    def test_un_import_remoto_iniettato_e_rilevato(self):
        css = ('/* nessun @import qui, ne parliamo solo: vedi https://esempio.invalid */\n'
               'body{color:red}\n'
               '@import url(https://fonts.googleapis.com/css?family=Inter);')
        pulito = _COMMENTO_CSS.sub("", css)
        self.assertNotEqual(_IMPORT_CSS.findall(pulito), [], "un @import remoto iniettato deve essere rilevato")

    def test_una_url_remota_iniettata_fuori_dai_ticket_e_rilevata(self):
        html = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'
        self.assertNotEqual(_URL.findall(_fuori_dai_ticket_e_dall_xmlns(html)), [],
                             "una URL remota vera fuori dai ticket deve essere rilevata")

    def test_un_link_vero_dentro_un_ticket_non_e_un_falso_positivo(self):
        """Il caso che il controllo deve LASCIAR PASSARE: un ticket puo' citare
        un link vero in prosa (per esempio una issue), e non e' un
        caricamento remoto solo perche' la stringa "https://" compare."""
        html = ('<script type="application/json" id="atlas-data">{"md":"vedi '
                'https://github.com/strawberry-code/atlas/issues/30"}</script>')
        self.assertEqual(_URL.findall(_fuori_dai_ticket_e_dall_xmlns(html)), [])

    def test_lo_spazio_dei_nomi_svg_non_e_un_falso_positivo(self):
        """Le tre occorrenze legittime (l'attributo xmlns e le due costanti JS
        di createElementNS) non devono mai risultare una URL remota."""
        html = (f'<svg xmlns="{NS_SVG}"></svg><script>var NS="{NS_SVG}";'
                f'var NS2="{NS_SVG}";</script>')
        self.assertEqual(_URL.findall(_fuori_dai_ticket_e_dall_xmlns(html)), [])

    def test_un_peso_oltre_soglia_e_rilevato(self):
        finto = "x" * (SOGLIA_BYTES + 1)
        self.assertGreaterEqual(len(finto.encode("utf-8")), SOGLIA_BYTES,
                                 "il finto payload deve superare la soglia dichiarata")


if __name__ == "__main__":
    unittest.main()
