"""D08: il capability token D01 (~270 byte) non entra nel callback_data di
un bottone Telegram, che ne accetta al massimo 64. Questo test misura la
lunghezza di cio' che finisce davvero su callback_data dopo il passaggio da
'capability_store.StoreCapability', su una capability costruita con codice
vero (payload/core/capability.emetti), non con una stringa finta: e' la
verifica che il difetto misurato da D07 resta chiuso.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

from core import capability  # noqa: E402

import capability_store  # noqa: E402

LIMITE_CALLBACK_DATA_TELEGRAM = 64

CHIAVE = "una-chiave-hmac-di-progetto"


def _capability_reale() -> str:
    """Una capability con campi della taglia di un uso vero: lo slug di
    questo stesso progetto, un run_id nel formato di run_state.py
    (uuid4().hex[:12]), un'azione con l'id/label tipici di
    interactions.py."""
    exp = (datetime.now().astimezone() + timedelta(minutes=5)).isoformat(timespec="seconds")
    return capability.emetti(
        CHIAVE, graph="260830-atlas-interactions", run_id="5d2048c9ffbb",
        interaction_id="I001", action_id="confirm", exp=exp)


class CallbackDataSottoIlLimiteTelegram(unittest.TestCase):
    def test_una_capability_reale_pesa_piu_di_64_byte(self):
        """Prova che il difetto misurato da D07 esiste ancora a monte: se
        questa assunzione smettesse di valere il test sotto diventerebbe
        vacuo."""
        token = _capability_reale()
        self.assertGreater(len(token.encode("utf-8")), LIMITE_CALLBACK_DATA_TELEGRAM)

    def test_lidentificativo_registrato_sta_nel_limite(self):
        store = capability_store.StoreCapability()
        identificativo = store.registra(_capability_reale())
        self.assertLessEqual(len(identificativo.encode("utf-8")), LIMITE_CALLBACK_DATA_TELEGRAM)

    def test_lidentificativo_risolve_alla_capability_originale(self):
        """Il roundtrip completo: quel che lo store restituisce non e' un
        frammento tagliato a meta', e' il capability token per intero,
        verificabile con lo stesso capability.verifica che D06 chiama su un
        tap vero."""
        store = capability_store.StoreCapability()
        token = _capability_reale()
        identificativo = store.registra(token)

        risolto = store.preleva(identificativo)

        self.assertEqual(risolto, token)
        payload = capability.verifica(CHIAVE, risolto, consumati=capability.ConsumatiJti())
        self.assertEqual(payload["actionId"], "confirm")


class StoreCapabilityTest(unittest.TestCase):
    def test_identificativi_diversi_per_registrazioni_diverse(self):
        store = capability_store.StoreCapability()
        primo = store.registra("token-a")
        secondo = store.registra("token-b")
        self.assertNotEqual(primo, secondo)

    def test_preleva_e_monouso(self):
        store = capability_store.StoreCapability()
        identificativo = store.registra("il-token")
        self.assertEqual(store.preleva(identificativo), "il-token")
        self.assertIsNone(store.preleva(identificativo))  # gia' consumato

    def test_identificativo_sconosciuto_none(self):
        store = capability_store.StoreCapability()
        self.assertIsNone(store.preleva("non-esiste"))

    def test_capienza_limitata_scalza_il_piu_vecchio(self):
        store = capability_store.StoreCapability(capienza=2)
        primo = store.registra("token-1")
        store.registra("token-2")
        store.registra("token-3")  # scalza 'primo'
        self.assertIsNone(store.preleva(primo))

    def test_store_non_interpreta_il_contenuto_del_token(self):
        """Il contenuto del blob e' del tutto indifferente allo store: anche
        una stringa che non e' affatto un capability token valido si
        registra e si preleva senza che lo store se ne accorga (D01: il
        relay resta un puro instradatore anche per D08)."""
        store = capability_store.StoreCapability()
        identificativo = store.registra("non-un-token-valido")
        self.assertEqual(store.preleva(identificativo), "non-un-token-valido")


if __name__ == "__main__":
    unittest.main()
