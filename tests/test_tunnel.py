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
        self.assertFalse(registro.push("g", "r", {"a": 1}))

    def test_connetti_poi_push_arriva_alla_coda(self):
        registro = tunnel.RegistroTunnel()
        coda = registro.connetti("g", "r")
        self.assertTrue(registro.push("g", "r", {"a": 1}))
        self.assertEqual(coda.get_nowait(), {"a": 1})

    def test_sessioni_diverse_non_si_vedono(self):
        registro = tunnel.RegistroTunnel()
        coda_a = registro.connetti("g", "run-a")
        registro.connetti("g", "run-b")
        registro.push("g", "run-a", {"a": 1})
        self.assertEqual(coda_a.get_nowait(), {"a": 1})

    def test_push_arriva_a_tutte_le_connessioni_della_stessa_sessione(self):
        registro = tunnel.RegistroTunnel()
        coda_1 = registro.connetti("g", "r")
        coda_2 = registro.connetti("g", "r")
        registro.push("g", "r", {"a": 1})
        self.assertEqual(coda_1.get_nowait(), {"a": 1})
        self.assertEqual(coda_2.get_nowait(), {"a": 1})

    def test_disconnetti_rimuove_la_coda(self):
        registro = tunnel.RegistroTunnel()
        coda = registro.connetti("g", "r")
        registro.disconnetti("g", "r", coda)
        self.assertFalse(registro.push("g", "r", {"a": 1}))

    def test_disconnetti_su_sessione_ignota_non_solleva(self):
        registro = tunnel.RegistroTunnel()
        registro.disconnetti("ignota", "r", Queue())  # non solleva

    def test_sessioni_di_torna_i_runid_connessi_per_il_progetto(self):
        registro = tunnel.RegistroTunnel()
        registro.connetti("g", "run-a")
        registro.connetti("g", "run-b")
        registro.connetti("altro-progetto", "run-c")
        self.assertEqual(set(registro.sessioni_di("g")), {"run-a", "run-b"})

    def test_sessioni_di_progetto_senza_tunnel_e_vuoto(self):
        registro = tunnel.RegistroTunnel()
        self.assertEqual(registro.sessioni_di("nessuno"), [])


class CostruisciInstradamentoTest(unittest.TestCase):
    """Il sink D06 fra il webhook (chat_id) e il tunnel (graph, runId)."""

    def test_instrada_a_ogni_sessione_connessa_del_progetto(self):
        registro = tunnel.RegistroTunnel()
        coda_a = registro.connetti("g", "run-a")
        coda_b = registro.connetti("g", "run-b")
        sink = tunnel.costruisci_instradamento(lambda chat_id: "g", registro)
        sink({"chat_id": 42, "callback_data": "x"})
        self.assertEqual(coda_a.get_nowait(), {"chat_id": 42, "callback_data": "x"})
        self.assertEqual(coda_b.get_nowait(), {"chat_id": 42, "callback_data": "x"})

    def test_chat_non_associata_non_instrada_nulla(self):
        registro = tunnel.RegistroTunnel()
        registro.connetti("g", "run-a")
        sink = tunnel.costruisci_instradamento(lambda chat_id: None, registro)
        sink({"chat_id": 42})  # non solleva, non consegna
        self.assertEqual(registro.sessioni_di("g"), ["run-a"])

    def test_progetto_senza_tunnel_aperto_perde_levento(self):
        registro = tunnel.RegistroTunnel()
        sink = tunnel.costruisci_instradamento(lambda chat_id: "g-senza-tunnel", registro)
        sink({"chat_id": 42})  # non solleva

    def test_chat_id_non_intero_non_instrada_nulla(self):
        registro = tunnel.RegistroTunnel()
        chiamate = []
        sink = tunnel.costruisci_instradamento(lambda chat_id: chiamate.append(chat_id), registro)
        sink({"chat_id": "non-un-intero"})
        self.assertEqual(chiamate, [])


if __name__ == "__main__":
    unittest.main()
