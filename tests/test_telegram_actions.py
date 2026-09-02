"""D06: dal tap Telegram (evento del tunnel) alla risoluzione dell'Interaction,
con la capability come lasciapassare e l'aggiornamento del messaggio come
esito osservabile."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import capability, interactions, mutate, relay_client, telegram_actions
from core.config import Workspace
from core.store import load

CHIAVE = "una-chiave-hmac-di-progetto"


def _exp(delta: timedelta = timedelta(minutes=5)) -> str:
    return (datetime.now().astimezone() + delta).isoformat(timespec="seconds")


class TelegramActionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ws = Workspace(self.tmp / ".atlas")
        self.ref = mutate.create_graph(self.ws, "prova", "Prova", "Verifica D06")
        with mutate.editing(self.ref) as graph:
            mutate.add_node(graph, "A01", "Nodo", "A", "Domanda")
        self.actions = [
            {"id": "confirm", "label": "Conferma", "effect": "resume"},
            {"id": "decline", "label": "Rifiuta", "effect": "cancel"},
        ]
        with mutate.editing(self.ref) as graph:
            self.interaction = interactions.open_interaction(
                graph, run_id="run-01", node_id="A01", event="decision-required",
                summary="Serve una decisione.", allowed_actions=self.actions,
                expires_at=_exp(timedelta(days=1)), idempotency_key="run-01:A01:decision")
        self.config = relay_client.TunnelConfig(base_url="https://relay.test", token="bearer")
        self.inviati = []

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _opener(self):
        def opener(richiesta, timeout=None):
            import json as _json

            class _Vuota:
                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False
            self.inviati.append(_json.loads(richiesta.data))
            return _Vuota()
        return opener

    def _token(self, action_id="confirm", **override):
        campi = dict(graph=self.ref.slug, run_id="run-01",
                    interaction_id=self.interaction["id"], action_id=action_id, exp=_exp())
        campi.update(override)
        return capability.emetti(CHIAVE, **campi)

    def _gestore(self, run_id="run-01"):
        return telegram_actions.gestore(self.ref, run_id, CHIAVE, self.config,
                                        opener=self._opener())

    def _record(self):
        return next(r for r in load(self.ref.json_path)["interactions"]
                   if r["id"] == self.interaction["id"])

    def test_tap_valido_risolve_e_aggiorna_il_messaggio(self):
        on_event = self._gestore()
        on_event({"kind": "callback", "callback_data": self._token(), "chat_id": 1, "message_id": 2})

        record = self._record()
        self.assertEqual(record["status"], "resolved")
        self.assertEqual(record["resolution"], {"action": "confirm", "effect": "resume"})
        self.assertEqual(self.inviati, [{"chatId": 1, "messageId": 2, "text": "Fatto: Conferma."}])

    def test_tap_su_interaction_gia_risolta_non_riapplica_e_avvisa(self):
        on_event = self._gestore()
        primo_token = self._token()
        on_event({"kind": "callback", "callback_data": primo_token, "chat_id": 1, "message_id": 2})
        self.inviati.clear()

        secondo_token = self._token(action_id="decline")
        on_event({"kind": "callback", "callback_data": secondo_token, "chat_id": 1, "message_id": 2})

        record = self._record()
        self.assertEqual(record["resolution"], {"action": "confirm", "effect": "resume"})  # invariato
        self.assertEqual(len(self.inviati), 1)
        self.assertIn("non è più valida", self.inviati[0]["text"])

    def test_capability_non_valida_non_tocca_il_ledger_ne_manda_messaggi(self):
        on_event = self._gestore()
        on_event({"kind": "callback", "callback_data": "non-un-token", "chat_id": 1, "message_id": 2})

        self.assertEqual(self._record()["status"], "open")
        self.assertEqual(self.inviati, [])

    def test_capability_di_unaltra_sessione_viene_scartata(self):
        on_event = self._gestore(run_id="run-diverso")
        on_event({"kind": "callback", "callback_data": self._token(), "chat_id": 1, "message_id": 2})

        self.assertEqual(self._record()["status"], "open")
        self.assertEqual(self.inviati, [])

    def test_capability_di_un_altro_progetto_viene_scartata(self):
        on_event = self._gestore()
        token = self._token(graph="un-altro-progetto")
        on_event({"kind": "callback", "callback_data": token, "chat_id": 1, "message_id": 2})

        self.assertEqual(self._record()["status"], "open")
        self.assertEqual(self.inviati, [])

    def test_evento_non_callback_ignorato(self):
        on_event = self._gestore()
        on_event({"kind": "message", "chat_id": 1, "message_id": 2, "text": "ciao"})

        self.assertEqual(self._record()["status"], "open")
        self.assertEqual(self.inviati, [])

    def test_campi_mancanti_o_di_tipo_sbagliato_non_sollevano(self):
        on_event = self._gestore()
        on_event({"kind": "callback", "callback_data": self._token(), "chat_id": "non-intero", "message_id": 2})
        on_event({"kind": "callback", "chat_id": 1, "message_id": 2})  # nessun callback_data

        self.assertEqual(self._record()["status"], "open")
        self.assertEqual(self.inviati, [])

    def test_token_gia_consumato_una_volta_e_rifiutato_la_seconda(self):
        on_event = self._gestore()
        evento = {"kind": "callback", "callback_data": self._token(), "chat_id": 1, "message_id": 2}
        on_event(evento)
        self.inviati.clear()
        on_event(evento)  # stesso jti: la difesa in profondita' lo scarta prima del ledger

        self.assertEqual(self._record()["status"], "resolved")
        self.assertEqual(self.inviati, [])


if __name__ == "__main__":
    unittest.main()
