"""'serve_notify.avvisa': il canale locale agganciato alla ronda di 'atlas
serve' (C02). Il canale reale (notify_local) non si esercita qui: si inietta
un canale finto, cosi' la suite non apre davvero una notifica di sistema."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "payload"


class _CanaleFinto:
    identity = "local"

    def __init__(self):
        self.consegnate: list[str] = []

    def deliver(self, interaction):
        self.consegnate.append(interaction["id"])


class ServeNotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".atlas"
        shutil.copytree(SORGENTE, self.root)
        (self.root / "config.json").write_text(json.dumps({"project": "prova"}), encoding="utf-8")
        for cartella in ("graphs", "scripts"):
            (self.root / cartella).mkdir()
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        from core import channels, config, interactions, mutate, serve_notify
        self.channels, self.config = channels, config
        self.interactions, self.mutate = interactions, mutate
        self.serve_notify = serve_notify
        self.ws = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo di prova", "Verificare l'avviso.")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        shutil.rmtree(self.tmp)

    def _apri_interaction(self, interaction_id_atteso="I001"):
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, "A01", "Nodo", "A", "Domanda")
        with self.mutate.editing(self.ref) as g:
            record = self.interactions.open_interaction(
                g, run_id="run-01", node_id="A01", event="decision-required",
                summary="Serve una decisione per A01.",
                allowed_actions=[{"id": "confirm", "label": "Conferma", "effect": "resume"}],
                expires_at="2099-01-01T00:00:00+00:00",
                idempotency_key="run-01:A01:decision")
        return record["id"]

    def test_senza_interactions_non_consegna_niente(self):
        registro = self.channels.ChannelRegistry([_CanaleFinto()])
        self.serve_notify.avvisa(self.ref, registro)
        self.assertEqual([], registro.get("local").consegnate)

    def test_una_interaction_aperta_arriva_al_canale_locale(self):
        interaction_id = self._apri_interaction()
        canale = _CanaleFinto()
        registro = self.channels.ChannelRegistry([canale])

        self.serve_notify.avvisa(self.ref, registro)

        self.assertEqual([interaction_id], canale.consegnate)

    def test_una_seconda_ronda_non_riconsegna_la_stessa_interaction(self):
        self._apri_interaction()
        canale = _CanaleFinto()
        registro = self.channels.ChannelRegistry([canale])

        self.serve_notify.avvisa(self.ref, registro)
        self.serve_notify.avvisa(self.ref, registro)

        self.assertEqual(1, len(canale.consegnate))

    def test_un_notify_state_corrotto_non_solleva(self):
        self._apri_interaction()
        self.ref.notify_state_path.write_text("{non-json", encoding="utf-8")
        registro = self.channels.ChannelRegistry([_CanaleFinto()])

        self.serve_notify.avvisa(self.ref, registro)   # non deve sollevare

    def test_senza_registro_esplicito_usa_il_canale_locale_di_default(self):
        # Nessuna Interaction aperta: verifica solo che il ramo di produzione
        # (notify_local.registry() reale) non venga nemmeno costruito quando
        # non c'e' nulla da consegnare, senza toccare l'utility di sistema.
        self.serve_notify.avvisa(self.ref)

    def test_canali_attivi_include_telegram_solo_se_relay_e_capability_configurati(self):
        self.assertNotIn("telegram", self.serve_notify._canali_attivi())
        os.environ.update({"RELAY_HTTPS_HOSTNAME": "relay.test", "ATLAS_RELAY_TOKEN_REF": "t",
                           "ATLAS_CAPABILITY_KEY_REF": "k"})
        try:
            self.assertIn("telegram", self.serve_notify._canali_attivi())
        finally:
            for chiave in ("RELAY_HTTPS_HOSTNAME", "ATLAS_RELAY_TOKEN_REF", "ATLAS_CAPABILITY_KEY_REF"):
                os.environ.pop(chiave, None)

    def test_una_interaction_aperta_arriva_al_canale_telegram_appaiato(self):
        # 'local' e' sempre attivo (_canali_attivi): il registro deve
        # comunque servirlo, anche se qui interessa solo verificare telegram.
        interaction_id = self._apri_interaction()
        canale_locale = _CanaleFinto()
        canale_telegram = _CanaleFinto()
        canale_telegram.identity = "telegram"
        registro = self.channels.ChannelRegistry([canale_locale, canale_telegram])
        os.environ.update({"RELAY_HTTPS_HOSTNAME": "relay.test", "ATLAS_RELAY_TOKEN_REF": "t",
                           "ATLAS_CAPABILITY_KEY_REF": "k"})
        try:
            self.serve_notify.avvisa(self.ref, registro)
        finally:
            for chiave in ("RELAY_HTTPS_HOSTNAME", "ATLAS_RELAY_TOKEN_REF", "ATLAS_CAPABILITY_KEY_REF"):
                os.environ.pop(chiave, None)
        self.assertEqual([interaction_id], canale_telegram.consegnate)


if __name__ == "__main__":
    unittest.main()
