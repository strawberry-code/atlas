"""Test del long polling verso Telegram (G01): nessuna rete reale, 'opener'
sempre iniettato. Il traduttore condiviso con il webhook e' gia' coperto da
test_telegram_webhook.py: qui si verifica solo il ciclo (offset, backoff,
avvio del thread), non la traduzione dell'update.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import telegram_polling as tp


class _FakeRisposta:
    def __init__(self, corpo: dict) -> None:
        self._corpo = json.dumps(corpo).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._corpo


class FakeOpener:
    """Coda di risposte pianificate: un dict diventa una risposta JSON ok,
    un'eccezione viene sollevata cosi' com'e'. Registra ogni richiesta per
    ispezionarne l'offset chiesto."""

    def __init__(self, risposte: list) -> None:
        self._risposte = list(risposte)
        self.chiamate: list = []

    def __call__(self, richiesta, timeout):
        self.chiamate.append(richiesta)
        risposta = self._risposte.pop(0)
        if isinstance(risposta, Exception):
            raise risposta
        return _FakeRisposta(risposta)

    def offset_richiesto(self, indice: int) -> str:
        query = urllib.parse.urlsplit(self.chiamate[indice].full_url).query
        return urllib.parse.parse_qs(query)["offset"][0]


class OffsetStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.percorso = Path(self._tmp.name) / "offset.json"

    def test_zero_se_il_file_non_esiste(self):
        self.assertEqual(tp.OffsetStore(self.percorso).leggi(), 0)

    def test_zero_se_il_file_e_corrotto(self):
        self.percorso.write_text("non e' json", encoding="utf-8")
        self.assertEqual(tp.OffsetStore(self.percorso).leggi(), 0)

    def test_avanza_persiste_e_sopravvive_a_una_nuova_istanza(self):
        tp.OffsetStore(self.percorso).avanza(42)
        self.assertEqual(tp.OffsetStore(self.percorso).leggi(), 42)


class GetUpdatesTest(unittest.TestCase):
    def test_risultato_ok_torna_la_lista(self):
        opener = FakeOpener([{"ok": True, "result": [{"update_id": 1}]}])
        self.assertEqual(tp._get_updates("TOKEN", 0, opener, timeout=1), [{"update_id": 1}])

    def test_ok_senza_result_torna_lista_vuota(self):
        opener = FakeOpener([{"ok": True}])
        self.assertEqual(tp._get_updates("TOKEN", 0, opener, timeout=1), [])

    def test_non_ok_solleva_value_error(self):
        opener = FakeOpener([{"ok": False, "description": "unauthorized"}])
        with self.assertRaises(ValueError):
            tp._get_updates("TOKEN", 0, opener, timeout=1)

    def test_offset_e_token_finiscono_nella_richiesta(self):
        opener = FakeOpener([{"ok": True, "result": []}])
        tp._get_updates("BOT:TOKEN", 7, opener, timeout=1)
        self.assertIn("BOT:TOKEN", opener.chiamate[0].full_url)
        self.assertEqual(opener.offset_richiesto(0), "7")


class CicloPollingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = tp.OffsetStore(Path(self._tmp.name) / "offset.json")

    def test_processa_ogni_update_e_avanza_loffset(self):
        fermo = threading.Event()
        processati = []

        def processa(update):
            processati.append(update)
            fermo.set()

        opener = FakeOpener([{"ok": True, "result": [{"update_id": 5, "message": {}}]}])
        tp.ciclo_polling("TOKEN", processa, self.store, fermo, opener=opener,
                          timeout=1, attesa_errore=0)
        self.assertEqual(processati, [{"update_id": 5, "message": {}}])
        self.assertEqual(self.store.leggi(), 6)

    def test_secondo_giro_chiede_loffset_avanzato_dal_primo(self):
        fermo = threading.Event()
        contatore = {"n": 0}

        def processa(update):
            contatore["n"] += 1
            if contatore["n"] == 2:
                fermo.set()

        opener = FakeOpener([
            {"ok": True, "result": [{"update_id": 5, "message": {}}]},
            {"ok": True, "result": [{"update_id": 9, "message": {}}]},
        ])
        tp.ciclo_polling("TOKEN", processa, self.store, fermo, opener=opener,
                          timeout=1, attesa_errore=0)
        self.assertEqual(len(opener.chiamate), 2)
        self.assertEqual(opener.offset_richiesto(0), "0")
        self.assertEqual(opener.offset_richiesto(1), "6")
        self.assertEqual(self.store.leggi(), 10)

    def test_lotto_vuoto_non_avanza_loffset(self):
        fermo = threading.Event()

        def processa(update):
            raise AssertionError("un lotto vuoto non produce update da processare")

        def _opener(richiesta, timeout):
            fermo.set()  # nessun altro giro dopo questa risposta vuota
            return _FakeRisposta({"ok": True, "result": []})

        tp.ciclo_polling("TOKEN", processa, self.store, fermo, opener=_opener,
                          timeout=1, attesa_errore=0)
        self.assertEqual(self.store.leggi(), 0)

    def test_errore_di_rete_non_ferma_il_ciclo_e_ritenta(self):
        fermo = threading.Event()

        def processa(update):
            fermo.set()

        opener = FakeOpener([
            urllib.error.URLError("giu'"),
            {"ok": True, "result": [{"update_id": 1, "message": {}}]},
        ])
        tp.ciclo_polling("TOKEN", processa, self.store, fermo, opener=opener,
                          timeout=1, attesa_errore=0)
        self.assertEqual(len(opener.chiamate), 2)

    def test_risposta_non_ok_e_trattata_come_errore_e_si_ritenta(self):
        fermo = threading.Event()

        def processa(update):
            fermo.set()

        opener = FakeOpener([
            {"ok": False, "description": "conflict: webhook ancora attivo"},
            {"ok": True, "result": [{"update_id": 1, "message": {}}]},
        ])
        tp.ciclo_polling("TOKEN", processa, self.store, fermo, opener=opener,
                          timeout=1, attesa_errore=0)
        self.assertEqual(len(opener.chiamate), 2)

    def test_fermo_gia_impostato_non_chiama_mai_lopener(self):
        fermo = threading.Event()
        fermo.set()
        opener = FakeOpener([])
        tp.ciclo_polling("TOKEN", lambda u: None, self.store, fermo, opener=opener,
                          timeout=1, attesa_errore=0)
        self.assertEqual(opener.chiamate, [])


class AvviaPollerDaAmbienteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.percorso = Path(self._tmp.name) / "offset.json"

    def test_none_senza_token(self):
        fermo = threading.Event()
        self.assertIsNone(tp.avvia_poller_da_ambiente({}, lambda u: None, fermo))

    def test_avvia_un_thread_demone_e_si_ferma_su_fermo(self):
        fermo = threading.Event()
        processati = []

        def processa(update):
            processati.append(update)
            fermo.set()

        opener = FakeOpener([{"ok": True, "result": [{"update_id": 3, "message": {}}]}])
        thread = tp.avvia_poller_da_ambiente(
            {"TELEGRAM_BOT_TOKEN_REF": "BOT:TOKEN"}, processa, fermo,
            state_path=self.percorso, opener=opener)
        self.assertIsNotNone(thread)
        self.assertTrue(thread.daemon)
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(processati, [{"update_id": 3, "message": {}}])


if __name__ == "__main__":
    unittest.main()
