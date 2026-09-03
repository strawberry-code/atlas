"""Test del lato relay del tunnel D03 in isolamento: verifica del bearer e
RegistroTunnel. La traduzione HTTP (endpoint /tunnel) e' testata a parte in
tests/test_relay.py (TunnelSulRelay), qui non c'e' nessun server acceso.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from queue import Queue

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import tunnel

TOKEN = "il-bearer-del-tunnel"


class VerificaBearer(unittest.TestCase):
    def test_ok_con_bearer_giusto(self):
        tunnel.verifica_bearer(f"Bearer {TOKEN}", TOKEN)  # non solleva

    def test_rifiuta_senza_header(self):
        with self.assertRaises(tunnel.TunnelRejected):
            tunnel.verifica_bearer(None, TOKEN)

    def test_rifiuta_senza_prefisso_bearer(self):
        with self.assertRaises(tunnel.TunnelRejected):
            tunnel.verifica_bearer(TOKEN, TOKEN)

    def test_rifiuta_token_sbagliato(self):
        with self.assertRaises(tunnel.TunnelRejected):
            tunnel.verifica_bearer("Bearer sbagliato", TOKEN)


class RegistroTunnelTest(unittest.TestCase):
    def test_push_senza_connessioni_non_consegna_nulla(self):
        registro = tunnel.RegistroTunnel()
        self.assertFalse(registro.push("installazione", {"a": 1}))

    def test_connetti_poi_push_arriva_alla_coda(self):
        registro = tunnel.RegistroTunnel()
        coda = registro.connetti("installazione")
        self.assertTrue(registro.push("installazione", {"a": 1}))
        self.assertEqual(coda.get_nowait(), {"a": 1})

    def test_installazioni_diverse_non_si_vedono(self):
        registro = tunnel.RegistroTunnel()
        coda_a = registro.connetti("mac-a")
        registro.connetti("mac-b")
        registro.push("mac-a", {"a": 1})
        self.assertEqual(coda_a.get_nowait(), {"a": 1})

    def test_push_arriva_a_tutte_le_connessioni_della_stessa_installazione(self):
        registro = tunnel.RegistroTunnel()
        coda_1 = registro.connetti("installazione")
        coda_2 = registro.connetti("installazione")
        registro.push("installazione", {"a": 1})
        self.assertEqual(coda_1.get_nowait(), {"a": 1})
        self.assertEqual(coda_2.get_nowait(), {"a": 1})

    def test_disconnetti_rimuove_la_coda(self):
        registro = tunnel.RegistroTunnel()
        coda = registro.connetti("installazione")
        registro.disconnetti("installazione", coda)
        self.assertFalse(registro.push("installazione", {"a": 1}))

    def test_disconnetti_su_installazione_ignota_non_solleva(self):
        registro = tunnel.RegistroTunnel()
        registro.disconnetti("ignota", Queue())  # non solleva


class CostruisciInstradamentoTest(unittest.TestCase):
    """Il sink D06 fra il webhook (chat_id) e la sola linea aperta
    dell'installazione risolta, a nessun'altra (A05)."""

    def test_instrada_alla_sola_linea_dell_installazione_risolta(self):
        registro = tunnel.RegistroTunnel()
        coda_giusta = registro.connetti("installazione")
        coda_altra = registro.connetti("altra-installazione")
        sink = tunnel.costruisci_instradamento(lambda chat_id: "installazione", registro)
        sink({"chat_id": 42, "callback_data": "x"})
        self.assertEqual(coda_giusta.get_nowait(), {"chat_id": 42, "callback_data": "x"})
        self.assertTrue(coda_altra.empty())

    def test_chat_non_associata_non_instrada_nulla(self):
        registro = tunnel.RegistroTunnel()
        registro.connetti("installazione")
        sink = tunnel.costruisci_instradamento(lambda chat_id: None, registro)
        sink({"chat_id": 42})  # non solleva, non consegna

    def test_installazione_senza_tunnel_aperto_perde_levento(self):
        registro = tunnel.RegistroTunnel()
        sink = tunnel.costruisci_instradamento(lambda chat_id: "senza-tunnel", registro)
        sink({"chat_id": 42})  # non solleva

    def test_chat_id_non_intero_non_instrada_nulla(self):
        registro = tunnel.RegistroTunnel()
        chiamate = []
        sink = tunnel.costruisci_instradamento(lambda chat_id: chiamate.append(chat_id), registro)
        sink({"chat_id": "non-un-intero"})
        self.assertEqual(chiamate, [])


if __name__ == "__main__":
    unittest.main()
