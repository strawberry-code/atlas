"""Verifica il canale Himalaya (email, C03): come si compone il messaggio, come
si costruisce l'argv del comando, i guasti permanenti dichiarati (binario
assente, destinatario non configurato) e il rispetto del contratto
'channels.Channel' usato dal coordinatore (C01)."""
from __future__ import annotations

import os
import sys
import unittest
from email import message_from_bytes, policy
from pathlib import Path
from unittest import mock

SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))

from core import notify_himalaya  # noqa: E402
from core.retry import PermanentError  # noqa: E402


def _interaction(**over):
    base = {
        "id": "I001", "nodeId": "B02", "runId": "run-01",
        "event": "decision-required", "summary": "Serve una decisione per B02.",
        "expiresAt": "2099-01-01T00:00:00+00:00",
        "allowedActions": [{"id": "confirm", "label": "Conferma", "effect": "resume"}],
    }
    base.update(over)
    return base


class Messaggio(unittest.TestCase):
    def test_subject_porta_nodo_ed_etichetta_evento(self):
        raw = notify_himalaya._messaggio(_interaction(), "dest@example.com")
        msg = message_from_bytes(raw, policy=policy.default)
        self.assertEqual("Atlas · B02 · decisione richiesta", msg["Subject"])
        self.assertEqual("dest@example.com", msg["To"])

    def test_corpo_riporta_summary_run_scadenza_e_azioni(self):
        raw = notify_himalaya._messaggio(_interaction(), "dest@example.com")
        corpo = message_from_bytes(raw, policy=policy.default).get_content()
        self.assertIn("Serve una decisione per B02.", corpo)
        self.assertIn("run-01", corpo)
        self.assertIn("2099-01-01T00:00:00+00:00", corpo)
        self.assertIn("Conferma", corpo)

    def test_evento_sconosciuto_passa_cosi_com_e(self):
        raw = notify_himalaya._messaggio(_interaction(event="qualcosa-di-nuovo"), "dest@example.com")
        self.assertIn("qualcosa-di-nuovo", message_from_bytes(raw, policy=policy.default)["Subject"])


class Argv(unittest.TestCase):
    def test_senza_account_non_aggiunge_lo_switch(self):
        self.assertEqual(["himalaya", "message", "send"], notify_himalaya._argv(None))

    def test_con_account_aggiunge_lo_switch(self):
        self.assertEqual(["himalaya", "message", "send", "-a", "icloud"],
                         notify_himalaya._argv("icloud"))


class Esecuzione(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_senza_destinatario_e_un_guasto_permanente(self):
        os.environ.pop(notify_himalaya.ENV_TO, None)
        chiamate = []
        canale = notify_himalaya.HimalayaChannel(runner=lambda *a: chiamate.append(a))
        with self.assertRaises(PermanentError):
            canale.deliver(_interaction())
        self.assertEqual([], chiamate)

    def test_deliver_passa_argv_e_messaggio_grezzo_al_runner(self):
        os.environ[notify_himalaya.ENV_TO] = "dest@example.com"
        os.environ.pop(notify_himalaya.ENV_ACCOUNT, None)
        chiamate = []
        canale = notify_himalaya.HimalayaChannel(runner=lambda argv, msg: chiamate.append((argv, msg)))
        canale.deliver(_interaction())
        self.assertEqual(1, len(chiamate))
        argv, messaggio = chiamate[0]
        self.assertEqual(["himalaya", "message", "send"], argv)
        self.assertIn(b"B02", messaggio)

    def test_deliver_rispetta_l_account_configurato(self):
        os.environ[notify_himalaya.ENV_TO] = "dest@example.com"
        os.environ[notify_himalaya.ENV_ACCOUNT] = "icloud"
        chiamate = []
        canale = notify_himalaya.HimalayaChannel(runner=lambda argv, msg: chiamate.append(argv))
        canale.deliver(_interaction())
        self.assertIn("icloud", chiamate[0])

    def test_binario_assente_e_un_guasto_permanente_non_ritentabile(self):
        with mock.patch.object(notify_himalaya, "subprocess") as finto:
            finto.run.side_effect = FileNotFoundError("himalaya")
            with self.assertRaises(PermanentError):
                notify_himalaya._esegui(["himalaya", "message", "send"], b"...")

    def test_uscita_diversa_da_zero_solleva_con_lo_stderr_nel_messaggio(self):
        with mock.patch.object(notify_himalaya, "subprocess") as finto:
            finto.run.return_value = mock.Mock(returncode=1, stderr=b"smtp timeout")
            with self.assertRaisesRegex(RuntimeError, "smtp timeout"):
                notify_himalaya._esegui(["himalaya", "message", "send"], b"...")

    def test_esegui_passa_il_messaggio_come_stdin(self):
        with mock.patch.object(notify_himalaya, "subprocess") as finto:
            finto.run.return_value = mock.Mock(returncode=0, stderr=b"")
            notify_himalaya._esegui(["himalaya", "message", "send"], b"raw-email")
        self.assertEqual(b"raw-email", finto.run.call_args.kwargs.get("input"))


class Registro(unittest.TestCase):
    def test_registry_registra_il_canale_himalaya_sotto_la_sua_identita(self):
        reg = notify_himalaya.registry()
        self.assertEqual(notify_himalaya.IDENTITY, reg.get("himalaya").identity)

    def test_registry_accetta_un_canale_finto_per_i_test(self):
        finto = notify_himalaya.HimalayaChannel(runner=lambda *a: None)
        reg = notify_himalaya.registry(finto)
        self.assertIs(finto, reg.get("himalaya"))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))


if __name__ == "__main__":
    unittest.main()
