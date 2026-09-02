"""Verifica il canale locale (avvisi di sistema, C02): quale comando parte per
piattaforma, come si comporta un'utility assente o che fallisce, e che il
canale rispetta il contratto 'channels.Channel' usato dal coordinatore (C01)."""
from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from unittest import mock

SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))

from core import notify_local  # noqa: E402
from core.retry import PermanentError  # noqa: E402


def _interaction(**over):
    base = {"id": "I001", "nodeId": "B02", "summary": "Serve una decisione per B02."}
    base.update(over)
    return base


class Comando(unittest.TestCase):
    def test_darwin_usa_osascript_con_titolo_e_corpo(self):
        with mock.patch.object(notify_local.sys, "platform", "darwin"):
            argv = notify_local._comando("Atlas · B02", "Serve una decisione.")
        self.assertEqual(["osascript", "-e"], argv[:2])
        self.assertIn('display notification "Serve una decisione."', argv[2])
        self.assertIn('with title "Atlas · B02"', argv[2])

    def test_darwin_sfugge_virgolette_e_backslash_nella_stringa_applescript(self):
        with mock.patch.object(notify_local.sys, "platform", "darwin"):
            argv = notify_local._comando("Atlas", 'testo con "virgolette" e \\ backslash')
        script = argv[2]
        # Una stringa AppleScript mal chiusa romperebbe l'intero comando: qui basta
        # che le virgolette del contenuto compaiano precedute dal loro escape.
        self.assertIn('\\"virgolette\\"', script)
        self.assertIn("\\\\ backslash", script)

    def test_linux_usa_notify_send_con_argv_separata(self):
        with mock.patch.object(notify_local.sys, "platform", "linux"):
            argv = notify_local._comando("Atlas · B02", "Serve una decisione.")
        self.assertEqual(["notify-send", "--", "Atlas · B02", "Serve una decisione."], argv)

    def test_windows_incodifica_titolo_e_corpo_recuperabili_dallo_script(self):
        with mock.patch.object(notify_local.sys, "platform", "win32"):
            argv = notify_local._comando("Atlas · B02", "Serve una decisione.")
        self.assertEqual("-EncodedCommand", argv[-2])
        script = base64.b64decode(argv[-1]).decode("utf-16-le")
        titolo_b64 = base64.b64encode("Atlas · B02".encode("utf-8")).decode("ascii")
        corpo_b64 = base64.b64encode("Serve una decisione.".encode("utf-8")).decode("ascii")
        self.assertIn(titolo_b64, script)
        self.assertIn(corpo_b64, script)
        self.assertIn("NotifyIcon", script)


class Esecuzione(unittest.TestCase):
    def test_deliver_passa_titolo_col_nodo_e_corpo_col_summary(self):
        chiamate = []
        canale = notify_local.DesktopChannel(runner=chiamate.append)
        canale.deliver(_interaction())
        self.assertEqual(1, len(chiamate))
        argv = chiamate[0]
        self.assertTrue(any("B02" in parte for parte in argv))
        self.assertTrue(any("Serve una decisione per B02." in parte for parte in argv))

    def test_binario_assente_e_un_guasto_permanente_non_ritentabile(self):
        with mock.patch.object(notify_local.sys, "platform", "linux"), \
             mock.patch.object(notify_local, "subprocess") as finto:
            finto.run.side_effect = FileNotFoundError("notify-send")
            with self.assertRaises(PermanentError):
                notify_local._esegui(["notify-send", "--", "t", "c"])

    def test_su_windows_non_attende_l_uscita_del_processo(self):
        with mock.patch.object(notify_local.sys, "platform", "win32"), \
             mock.patch.object(notify_local, "subprocess") as finto:
            notify_local._esegui(["powershell", "-EncodedCommand", "xxx"])
        finto.Popen.assert_called_once()
        finto.run.assert_not_called()

    def test_fuori_da_windows_attende_e_controlla_l_esito(self):
        with mock.patch.object(notify_local.sys, "platform", "darwin"), \
             mock.patch.object(notify_local, "subprocess") as finto:
            notify_local._esegui(["osascript", "-e", "script"])
        finto.run.assert_called_once()
        self.assertTrue(finto.run.call_args.kwargs.get("check"))
        finto.Popen.assert_not_called()


class Registro(unittest.TestCase):
    def test_registry_registra_il_canale_locale_sotto_la_sua_identita(self):
        reg = notify_local.registry()
        self.assertEqual(notify_local.IDENTITY, reg.get("local").identity)

    def test_registry_accetta_un_canale_finto_per_i_test(self):
        finto = notify_local.DesktopChannel(runner=lambda argv: None)
        reg = notify_local.registry(finto)
        self.assertIs(finto, reg.get("local"))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))


if __name__ == "__main__":
    unittest.main()
