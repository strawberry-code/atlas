"""Test dell'adapter Telegram lato relay (D04): verifica del webhook,
associazione, idempotenza dei callback. Nessuna rete reale: 'opener' e'
sempre iniettato dove serve chiamare l'API Telegram.
"""
from __future__ import annotations

import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import telegram_webhook as tw

SEGRETO = "il-segreto-del-webhook"


def _update_callback(update_id=1, callback_id="cb-1", chat_id=42, data="approve"):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "data": data,
            "message": {"message_id": 7, "chat": {"id": chat_id}},
        },
    }


def _update_messaggio(update_id=1, chat_id=42, text=None):
    messaggio = {"message_id": 3, "chat": {"id": chat_id}}
    if text is not None:
        messaggio["text"] = text
    return {"update_id": update_id, "message": messaggio}


class VerificaSegreto(unittest.TestCase):
    def test_accetta_segreto_giusto(self):
        tw.verifica_segreto(SEGRETO, SEGRETO)  # non solleva

    def test_rifiuta_segreto_assente(self):
        with self.assertRaises(tw.WebhookRejected):
            tw.verifica_segreto(None, SEGRETO)

    def test_rifiuta_segreto_sbagliato(self):
        with self.assertRaises(tw.WebhookRejected):
            tw.verifica_segreto("altro", SEGRETO)


class EstraiEvento(unittest.TestCase):
    def test_callback(self):
        evento = tw._estrai_evento(_update_callback())
        self.assertEqual(evento, {
            "kind": "callback",
            "callback_query_id": "cb-1",
            "chat_id": 42,
            "message_id": 7,
            "callback_data": "approve",
        })

    def test_messaggio(self):
        evento = tw._estrai_evento(_update_messaggio())
        self.assertEqual(evento, {"kind": "message", "chat_id": 42, "message_id": 3})

    def test_messaggio_con_testo_porta_il_testo(self):
        evento = tw._estrai_evento(_update_messaggio(text="/start abc123"))
        self.assertEqual(evento, {"kind": "message", "chat_id": 42, "message_id": 3,
                                   "text": "/start abc123"})

    def test_update_ignoto_none(self):
        self.assertIsNone(tw._estrai_evento({"update_id": 1, "my_chat_member": {}}))


class CodicePairingTest(unittest.TestCase):
    def test_start_con_codice(self):
        self.assertEqual(tw._codice_pairing({"text": "/start abc123"}), "abc123")

    def test_start_senza_codice_none(self):
        self.assertIsNone(tw._codice_pairing({"text": "/start"}))

    def test_messaggio_normale_none(self):
        self.assertIsNone(tw._codice_pairing({"text": "ciao"}))

    def test_senza_testo_none(self):
        self.assertIsNone(tw._codice_pairing({}))


class DedupCallbackTest(unittest.TestCase):
    def test_prima_volta_falso_seconda_vera(self):
        dedup = tw.DedupCallback()
        self.assertFalse(dedup.gia_visto(1))
        self.assertTrue(dedup.gia_visto(1))

    def test_capienza_limitata_fa_scadere_il_piu_vecchio(self):
        dedup = tw.DedupCallback(capienza=2)
        dedup.gia_visto(1)
        dedup.gia_visto(2)
        dedup.gia_visto(3)  # fa scadere 1
        self.assertFalse(dedup.gia_visto(1))


class MemoriaPairingTest(unittest.TestCase):
    def test_non_associato_di_default(self):
        self.assertFalse(tw.MemoriaPairing().is_paired(42))

    def test_associa_rende_paired(self):
        pairing = tw.MemoriaPairing()
        pairing.associa(42)
        self.assertTrue(pairing.is_paired(42))


class CodaTapTest(unittest.TestCase):
    def test_accumula_e_svuota(self):
        coda = tw.CodaTap()
        coda({"a": 1})
        coda({"a": 2})
        self.assertEqual(coda.preleva_tutti(), [{"a": 1}, {"a": 2}])
        self.assertEqual(coda.preleva_tutti(), [])


class GestoreWebhookTest(unittest.TestCase):
    def _gestore(self, paired_chat_ids=(42,), pairing_start=None):
        self.eventi = []
        self.risposte_callback = []
        return tw.GestoreWebhook(
            segreto_atteso=SEGRETO,
            pairing=tw.MemoriaPairing(paired_chat_ids),
            sink=self.eventi.append,
            answer_callback=self.risposte_callback.append,
            pairing_start=pairing_start,
        )

    def _corpo(self, update: dict) -> bytes:
        import json
        return json.dumps(update).encode("utf-8")

    def test_rifiuta_segreto_sbagliato_senza_toccare_sink(self):
        gestore = self._gestore()
        with self.assertRaises(tw.WebhookRejected):
            gestore.gestisci(self._corpo(_update_callback()), "sbagliato")
        self.assertEqual(self.eventi, [])
        self.assertEqual(self.risposte_callback, [])

    def test_callback_paired_arriva_al_sink_e_risponde(self):
        gestore = self._gestore()
        gestore.gestisci(self._corpo(_update_callback()), SEGRETO)
        self.assertEqual(len(self.eventi), 1)
        self.assertEqual(self.eventi[0]["chat_id"], 42)
        self.assertEqual(self.risposte_callback, ["cb-1"])

    def test_callback_non_paired_risponde_comunque_e_non_arriva_al_sink(self):
        gestore = self._gestore(paired_chat_ids=())
        with self.assertRaises(tw.UnpairedUser):
            gestore.gestisci(self._corpo(_update_callback()), SEGRETO)
        self.assertEqual(self.eventi, [])
        self.assertEqual(self.risposte_callback, ["cb-1"])  # ack Telegram gia' avvenuto

    def test_messaggio_non_chiama_answer_callback(self):
        gestore = self._gestore()
        gestore.gestisci(self._corpo(_update_messaggio()), SEGRETO)
        self.assertEqual(self.risposte_callback, [])
        self.assertEqual(len(self.eventi), 1)

    def test_redelivery_stesso_update_id_non_arriva_due_volte_al_sink(self):
        gestore = self._gestore()
        update = _update_callback()
        gestore.gestisci(self._corpo(update), SEGRETO)
        gestore.gestisci(self._corpo(update), SEGRETO)  # stessa update_id: redelivery
        self.assertEqual(len(self.eventi), 1)
        self.assertEqual(len(self.risposte_callback), 2)  # l'ack e' comunque idempotente lato Telegram

    def test_update_tipo_ignoto_non_solleva_e_non_tocca_sink(self):
        gestore = self._gestore()
        gestore.gestisci(self._corpo({"update_id": 9, "poll": {}}), SEGRETO)
        self.assertEqual(self.eventi, [])

    def test_corpo_non_json_rifiutato(self):
        gestore = self._gestore()
        with self.assertRaises(tw.WebhookRejected):
            gestore.gestisci(b"non e' json", SEGRETO)

    def test_start_chiama_pairing_start_e_non_tocca_sink_ne_pairing(self):
        chiamate = []
        gestore = self._gestore(paired_chat_ids=(),
                                 pairing_start=lambda codice, chat_id: chiamate.append((codice, chat_id)))
        update = _update_messaggio(chat_id=999, text="/start il-codice")
        gestore.gestisci(self._corpo(update), SEGRETO)  # non solleva UnpairedUser
        self.assertEqual(chiamate, [("il-codice", 999)])
        self.assertEqual(self.eventi, [])

    def test_start_senza_pairing_start_configurato_non_solleva(self):
        gestore = self._gestore(paired_chat_ids=())
        update = _update_messaggio(chat_id=999, text="/start il-codice")
        gestore.gestisci(self._corpo(update), SEGRETO)  # nessun gestore iniettato: ignorato, non un errore
        self.assertEqual(self.eventi, [])

    def test_start_redelivery_non_richiama_pairing_start_due_volte(self):
        chiamate = []
        gestore = self._gestore(paired_chat_ids=(),
                                 pairing_start=lambda codice, chat_id: chiamate.append((codice, chat_id)))
        update = _update_messaggio(update_id=7, chat_id=999, text="/start il-codice")
        gestore.gestisci(self._corpo(update), SEGRETO)
        gestore.gestisci(self._corpo(update), SEGRETO)
        self.assertEqual(len(chiamate), 1)

    def test_messaggio_normale_da_chat_non_associata_resta_unpaired(self):
        chiamate = []
        gestore = self._gestore(paired_chat_ids=(),
                                 pairing_start=lambda codice, chat_id: chiamate.append((codice, chat_id)))
        with self.assertRaises(tw.UnpairedUser):
            gestore.gestisci(self._corpo(_update_messaggio(chat_id=999, text="ciao")), SEGRETO)
        self.assertEqual(chiamate, [])
        self.assertEqual(self.eventi, [])

    def test_senza_capability_resolver_il_callback_data_passa_cosi_com_e(self):
        """Comportamento di prima di D08: se il confine non e' configurato,
        nessuno tocca il campo."""
        gestore = self._gestore()
        gestore.gestisci(self._corpo(_update_callback(data="il-token-per-intero")), SEGRETO)
        self.assertEqual(self.eventi[0]["callback_data"], "il-token-per-intero")

    def test_capability_resolver_sostituisce_lidentificativo_col_token(self):
        eventi, risposte = [], []
        gestore = tw.GestoreWebhook(
            segreto_atteso=SEGRETO, pairing=tw.MemoriaPairing((42,)), sink=eventi.append,
            answer_callback=risposte.append,
            capability_resolver=lambda ident: "il-token-vero" if ident == "id-corto" else None)
        gestore.gestisci(self._corpo(_update_callback(data="id-corto")), SEGRETO)
        self.assertEqual(eventi[0]["callback_data"], "il-token-vero")

    def test_capability_resolver_sconosciuto_non_arriva_al_sink(self):
        eventi, risposte = [], []
        gestore = tw.GestoreWebhook(
            segreto_atteso=SEGRETO, pairing=tw.MemoriaPairing((42,)), sink=eventi.append,
            answer_callback=risposte.append,
            capability_resolver=lambda ident: None)
        gestore.gestisci(self._corpo(_update_callback(data="id-mai-esistito")), SEGRETO)
        self.assertEqual(eventi, [])
        self.assertEqual(risposte, ["cb-1"])  # l'ack Telegram avviene comunque


class AnswerCallbackTest(unittest.TestCase):
    def test_chiama_endpoint_con_bot_token_e_callback_id(self):
        chiamate = []

        class FakeRisposta:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def opener(richiesta, timeout):
            chiamate.append(richiesta)
            return FakeRisposta()

        answer = tw.costruisci_answer_callback("BOT:TOKEN", opener=opener)
        answer("cb-1")
        self.assertEqual(len(chiamate), 1)
        self.assertIn("BOT:TOKEN", chiamate[0].full_url)
        self.assertIn("answerCallbackQuery", chiamate[0].full_url)

    def test_url_error_non_risale_al_chiamante(self):
        def opener(richiesta, timeout):
            raise urllib.error.URLError("giu'")

        answer = tw.costruisci_answer_callback("BOT:TOKEN", opener=opener)
        answer("cb-1")  # non deve sollevare


class ModificaMessaggioTest(unittest.TestCase):
    """editMessageText (D06): aggiorna un messaggio gia' inviato e ne toglie
    i bottoni, cosi' un secondo tap sullo stesso messaggio non produce un
    altro evento da instradare."""

    def test_chiama_editmessagetext_con_testo_e_senza_bottoni(self):
        chiamate = []

        class FakeRisposta:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def opener(richiesta, timeout):
            chiamate.append(richiesta)
            return FakeRisposta()

        modifica = tw.costruisci_modifica_messaggio("BOT:TOKEN", opener=opener)
        modifica(42, 7, "Fatto: Conferma.")

        self.assertEqual(len(chiamate), 1)
        self.assertIn("BOT:TOKEN", chiamate[0].full_url)
        self.assertIn("editMessageText", chiamate[0].full_url)
        import json as _json
        corpo = _json.loads(chiamate[0].data)
        self.assertEqual(corpo["chat_id"], 42)
        self.assertEqual(corpo["message_id"], 7)
        self.assertEqual(corpo["text"], "Fatto: Conferma.")
        self.assertEqual(corpo["reply_markup"], {"inline_keyboard": []})

    def test_url_error_non_risale_al_chiamante(self):
        def opener(richiesta, timeout):
            raise urllib.error.URLError("giu'")

        modifica = tw.costruisci_modifica_messaggio("BOT:TOKEN", opener=opener)
        modifica(42, 7, "x")  # non deve sollevare


class InviaBottoniTest(unittest.TestCase):
    """sendMessage con inline keyboard (D07): il deliver iniziale con un
    bottone per azione ammessa. A differenza di modifica/answer, il guasto
    NON deve essere assorbito: risale al chiamante (l'handler /tunnel/deliver
    del relay), che lo traduce in un 502 verso il client."""

    def test_chiama_sendmessage_con_inline_keyboard(self):
        chiamate = []

        class FakeRisposta:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def opener(richiesta, timeout):
            chiamate.append(richiesta)
            return FakeRisposta()

        invia = tw.costruisci_invia_bottoni("BOT:TOKEN", opener=opener)
        invia(42, "Serve una decisione", [("Conferma", "tok-1"), ("Rifiuta", "tok-2")])

        self.assertEqual(len(chiamate), 1)
        self.assertIn("BOT:TOKEN", chiamate[0].full_url)
        self.assertIn("sendMessage", chiamate[0].full_url)
        import json as _json
        corpo = _json.loads(chiamate[0].data)
        self.assertEqual(corpo["chat_id"], 42)
        self.assertEqual(corpo["text"], "Serve una decisione")
        self.assertEqual(corpo["reply_markup"], {"inline_keyboard": [
            [{"text": "Conferma", "callback_data": "tok-1"}],
            [{"text": "Rifiuta", "callback_data": "tok-2"}],
        ]})

    def test_url_error_risale_al_chiamante(self):
        def opener(richiesta, timeout):
            raise urllib.error.URLError("giu'")

        invia = tw.costruisci_invia_bottoni("BOT:TOKEN", opener=opener)
        with self.assertRaises(urllib.error.URLError):
            invia(42, "x", [("Conferma", "tok-1")])


class CostruisciGestoreDaAmbiente(unittest.TestCase):
    def test_none_senza_prerequisiti(self):
        self.assertIsNone(tw.costruisci_gestore_da_ambiente({}))

    def test_gestore_con_prerequisiti_completi(self):
        gestore = tw.costruisci_gestore_da_ambiente({
            "TELEGRAM_BOT_TOKEN_REF": "op://vault/telegram-bot-token",
            "TELEGRAM_WEBHOOK_SECRET_REF": SEGRETO,
        })
        self.assertIsInstance(gestore, tw.GestoreWebhook)

    def test_capability_resolver_passato_al_gestore(self):
        # Nessuna chiamata a gestisci() qui: farebbe scattare l'answer_callback
        # vero (rete verso api.telegram.org), non pertinente a questo test,
        # che verifica solo il passaggio del parametro attraverso il confine.
        gestore = tw.costruisci_gestore_da_ambiente(
            {"TELEGRAM_BOT_TOKEN_REF": "op://vault/telegram-bot-token",
             "TELEGRAM_WEBHOOK_SECRET_REF": SEGRETO},
            capability_resolver=lambda ident: f"risolto:{ident}")
        self.assertEqual(gestore._capability_resolver("id-corto"), "risolto:id-corto")


if __name__ == "__main__":
    unittest.main()
