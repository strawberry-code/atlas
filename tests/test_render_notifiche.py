"""Verifica il pannello Notifiche: bucketing di attenzione/attesa/risolte,
azioni al massimo due per card, run in attesa come contesto senza azioni."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))

_ENV_TELEGRAM = ("RELAY_HTTPS_HOSTNAME", "ATLAS_RELAY_TOKEN_REF", "ATLAS_CAPABILITY_KEY_REF")


class RifGrafo:
    """Sostituto minimo di config.Graph: render_notifiche usa run_state_path e
    (per la levetta di render_notif_telegram) workspace.config."""

    def __init__(self, cartella: Path, notify: dict | None = None):
        self.run_state_path = cartella / "run-state.json"
        self.notify_state_path = cartella / "notify-state.json"
        self.slug = "prova"
        self.workspace = SimpleNamespace(config={"notify": notify or {}})


class NotificheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ref = RifGrafo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    @staticmethod
    def _interaction(**over):
        base = {
            "id": "I001", "graph": "prova", "runId": "run-01", "nodeId": "B02",
            "event": "decision-required", "summary": "Serve una decisione per B02.",
            "allowedActions": [
                {"id": "confirm", "label": "Conferma", "effect": "resume"},
                {"id": "decline", "label": "Rifiuta", "effect": "cancel"},
            ],
            "expiresAt": "2026-08-31T12:00:00+02:00",
            "idempotencyKey": "run-01:B02:decision", "status": "open",
            "createdAt": "2026-08-31T11:45:00+02:00", "updatedAt": "2026-08-31T11:45:00+02:00",
            "resolution": None,
            "events": [{"at": "2026-08-31T11:45:00+02:00", "type": "opened", "by": "runner"}],
        }
        base.update(over)
        return base

    def test_una_interaction_aperta_finisce_in_attenzione_richiesta_col_badge(self):
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T11:50:00+02:00")
        data = {"interactions": [self._interaction()]}

        html = render_notifiche.panel(self.ref, data, now=momento)

        self.assertIn('<span class="badge">1</span>', html)
        self.assertIn("Serve una decisione per B02.", html)
        self.assertIn('data-action="confirm"', html)
        self.assertIn('data-action="decline"', html)

    def test_la_card_aperta_porta_l_id_dell_interaction_non_solo_del_nodo(self):
        """dashboard.js (C02) riconosce una card nuova da 'data-interaction' sul
        <li>, non dai bottoni: deve esserci anche quando la card non ha eventi."""
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T11:50:00+02:00")
        html = render_notifiche.panel(self.ref, {"interactions": [self._interaction()]}, now=momento)

        self.assertIn('data-interaction="I001"', html)

    def test_al_massimo_due_bottoni_azione_per_card_come_dal_record(self):
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T11:50:00+02:00")
        record = self._interaction(allowedActions=[{"id": "acknowledge", "label": "Preso atto", "effect": "ack"}])
        html = render_notifiche.panel(self.ref, {"interactions": [record]}, now=momento)

        self.assertEqual(1, html.count("data-action="))

    def test_senza_interactions_aperte_non_ce_badge(self):
        from core import render_notifiche

        html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())

        self.assertNotIn('class="badge"', html)

    def test_risolta_oggi_finisce_in_risolte_oggi_senza_azioni(self):
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T12:30:00+02:00")
        record = self._interaction(status="resolved", resolution={"action": "confirm", "effect": "resume"},
                                   updatedAt="2026-08-31T12:00:00+02:00",
                                   events=[
                                       {"at": "2026-08-31T11:45:00+02:00", "type": "opened", "by": "runner"},
                                       {"at": "2026-08-31T12:00:00+02:00", "type": "resolved", "by": "persona"},
                                   ])
        html = render_notifiche.panel(self.ref, {"interactions": [record]}, now=momento)

        self.assertIn('notif-chiusa', html)
        self.assertNotIn('data-action=', html)

    def test_risolta_ieri_non_compare_fra_le_risolte_oggi(self):
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T09:00:00+02:00")
        # creata e chiusa il giorno prima: 'age' la porta fuori dalla finestra di oggi
        record = self._interaction(status="cancelled",
                                   createdAt="2026-08-30T09:00:00+02:00",
                                   updatedAt="2026-08-30T09:05:00+02:00",
                                   events=[
                                       {"at": "2026-08-30T09:00:00+02:00", "type": "opened", "by": "runner"},
                                       {"at": "2026-08-30T09:05:00+02:00", "type": "cancelled", "by": "persona"},
                                   ])
        html = render_notifiche.panel(self.ref, {"interactions": [record]}, now=momento)

        self.assertNotIn("Serve una decisione per B02.", html)

    def test_risolta_oggi_ma_creata_ieri_finisce_comunque_in_risolte_oggi(self):
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T09:00:00+02:00")
        # aperta il giorno prima, chiusa stamattina: conta la data di risoluzione, non di apertura
        record = self._interaction(status="resolved", resolution={"action": "confirm", "effect": "resume"},
                                   createdAt="2026-08-30T18:00:00+02:00",
                                   updatedAt="2026-08-31T08:50:00+02:00",
                                   events=[
                                       {"at": "2026-08-30T18:00:00+02:00", "type": "opened", "by": "runner"},
                                       {"at": "2026-08-31T08:50:00+02:00", "type": "resolved", "by": "persona"},
                                   ])
        html = render_notifiche.panel(self.ref, {"interactions": [record]}, now=momento)

        self.assertIn("notif-chiusa", html)
        self.assertIn("Serve una decisione per B02.", html)

    def test_run_in_attesa_compare_come_contesto_senza_azioni(self):
        from core.run_state import RunState

        stato = RunState(self.ref.run_state_path, "prova", run_id="run-01")
        stato.start(1, ["B02"], 100.0)
        stato.event("attempt-waiting", 101.0, node="B02", status="waiting")

        from core import render_notifiche

        html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())

        self.assertIn("notif-contesto", html)
        self.assertIn("B02", html)
        self.assertNotIn("data-action=", html)

    def test_run_in_attesa_con_consegna_esaurita_mostra_la_riga_di_guasto(self):
        """SS7-ter/3: la mancata consegna si vede sulla dashboard, accanto al
        nodo in attesa, senza aprire un nuovo giro di retry (grilling 22)."""
        from core.notify import NotifyState
        from core.run_state import RunState

        stato = RunState(self.ref.run_state_path, "prova", run_id="run-01")
        stato.start(1, ["B02"], 100.0)
        stato.event("attempt-waiting", 101.0, node="B02", status="waiting")
        ledger = NotifyState(self.ref.notify_state_path, "prova")
        ledger.fail("I001::telegram", 3, "permanent-error", "bot bloccato", 101.0, delay=None)

        from core import render_notifiche

        html = render_notifiche.panel(self.ref, {"interactions": [self._interaction()]},
                                      now=datetime.fromisoformat("2026-08-31T11:50:00+02:00"))

        self.assertIn("notif-guasto", html)
        self.assertIn("telegram", html)

    def test_run_in_attesa_senza_consegne_esaurite_non_mostra_la_riga_di_guasto(self):
        from core.run_state import RunState

        stato = RunState(self.ref.run_state_path, "prova", run_id="run-01")
        stato.start(1, ["B02"], 100.0)
        stato.event("attempt-waiting", 101.0, node="B02", status="waiting")

        from core import render_notifiche

        html = render_notifiche.panel(self.ref, {"interactions": [self._interaction()]},
                                      now=datetime.fromisoformat("2026-08-31T11:50:00+02:00"))

        self.assertNotIn("notif-guasto", html)

    def test_senza_run_state_la_sezione_in_attesa_e_vuota(self):
        from core import render_notifiche

        html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())

        self.assertIn("notif-vuoto", html)

    def test_il_log_e_un_details_chiuso_con_gli_eventi_della_sola_card(self):
        """Contesto, artefatti e log sono consultazione su richiesta (A02): il
        log vive dentro un <details> nativo, chiuso finche' non lo si apre."""
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T11:50:00+02:00")
        html = render_notifiche.panel(self.ref, {"interactions": [self._interaction()]}, now=momento)

        self.assertIn("<details class=\"notif-log\">", html)
        self.assertNotIn(" open", html.split("<details", 1)[1].split(">", 1)[0])
        self.assertIn("runner", html)

    def test_senza_eventi_niente_details_di_log(self):
        from core import render_notifiche

        momento = datetime.fromisoformat("2026-08-31T11:50:00+02:00")
        record = self._interaction(events=[])
        html = render_notifiche.panel(self.ref, {"interactions": [record]}, now=momento)

        self.assertNotIn("notif-log", html)

    def test_il_pairing_telegram_e_un_bottone_unico_senza_campi(self):
        """D05: nessun input per token bot, chat ID, hostname o config - solo
        il bottone e uno span di stato che dashboard.js riempie da solo."""
        from core import render_notifiche

        html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())

        self.assertIn('class="pairing-telegram" data-pairing="telegram"', html)
        self.assertIn('class="pairing-stato"', html)
        self.assertNotIn("<input", html)
        self.assertIn("data-pairing-attesa=", html)
        self.assertIn("data-pairing-connesso=", html)
        self.assertIn("data-pairing-scaduto=", html)
        self.assertIn("data-pairing-rifiutato=", html)
        self.assertIn("data-pairing-senza-gestore=", html)

    def test_il_pairing_dice_la_promessa_nulla_sul_bottone(self):
        """A04/grilling 33: la promessa (servizio sperimentale, puo' finire
        quando il gestore vuole) sta accanto al bottone che attiva il
        pairing, sempre visibile, non solo dopo il tap e non in un doc."""
        from core import render_notifiche
        from core.strings import t

        html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())

        self.assertIn('class="pairing-nota"', html)
        self.assertIn(t("render.notif_pairing_promessa"), html)
        for termine_vietato in ("bearer", "capability", "graphId"):
            self.assertNotIn(termine_vietato, html)

    def test_senza_telegram_configurato_la_levetta_non_compare(self):
        """SS7-ter/1/SS11-11: chi lavora offline (nessun relay in ambiente,
        Telegram mai collegato su questa installazione) non deve vedere la
        levetta ne' trovarne traccia nel markup."""
        from core import render_notifiche
        from core.strings import t

        html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())

        self.assertNotIn("notif-muto", html)
        self.assertNotIn(t("render.notif_muto_silenzia"), html)

    def test_con_telegram_configurato_la_levetta_compare_accesa_di_default(self):
        from core import render_notifiche
        from core.strings import t

        os.environ.update({"RELAY_HTTPS_HOSTNAME": "relay.test", "ATLAS_RELAY_TOKEN_REF": "t",
                           "ATLAS_CAPABILITY_KEY_REF": "k"})
        try:
            html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())
        finally:
            for chiave in _ENV_TELEGRAM:
                os.environ.pop(chiave, None)

        self.assertIn('class="notif-muto" data-muto="on"', html)
        self.assertIn('aria-pressed="true"', html)
        self.assertIn(t("render.notif_muto_attivo"), html)
        self.assertIn(t("render.notif_muto_silenzia"), html)

    def test_con_la_levetta_spenta_nel_config_il_pannello_mostra_lo_stato_spento(self):
        from core import render_notifiche
        from core.strings import t

        self.ref.workspace.config["notify"]["telegram_enabled"] = False
        os.environ.update({"RELAY_HTTPS_HOSTNAME": "relay.test", "ATLAS_RELAY_TOKEN_REF": "t",
                           "ATLAS_CAPABILITY_KEY_REF": "k"})
        try:
            html = render_notifiche.panel(self.ref, {"interactions": []}, now=datetime.now().astimezone())
        finally:
            for chiave in _ENV_TELEGRAM:
                os.environ.pop(chiave, None)

        self.assertIn('class="notif-muto" data-muto="off"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn(t("render.notif_muto_silenziato"), html)
        self.assertIn(t("render.notif_muto_riattiva"), html)


if __name__ == "__main__":
    unittest.main()
