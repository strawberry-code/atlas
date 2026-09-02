"""Store del relay per il callback_data Telegram (D08): un capability token
D01 reale pesa circa 270 byte, Telegram accetta al massimo 64 byte in
'callback_data' (verificato con codice vero da D07). Il rimedio sta nel
protocollo, non nel canale: sul bottone va un identificativo corto e opaco
(qui, 'secrets.token_urlsafe'), la capability vera resta qui, nello store del
relay, restituita una sola volta quando il tap arriva.

Questo store non decide nulla sull'autorizzazione (D01 resta intatto): non
legge ne' verifica il contenuto del token, lo tratta come un blob opaco
esattamente come faceva prima il callback_data stesso. Un identificativo
sconosciuto, scaduto (scalzato dalla capienza limitata) o gia' consumato
(prelevato una volta) non trova piu' nulla qui e si scarta un passo prima di
raggiungere il client, con lo stesso effetto pratico (nessuna traccia,
nessuna azione) di un capability token invalido scartato oggi da
'payload/core/capability.py'. Un relay compromesso puo' al piu' rigiocare un
identificativo che ha gia' emesso lui stesso, cosa che 'payload/core/
capability.py' respinge comunque a valle (jti monouso, transizione atomica
del ledger): questo store non e' una seconda fonte di autorizzazione.

Capienza limitata come 'DedupCallback' (D04, relay/telegram_webhook.py): non
serve una scadenza esplicita ne' l'orologio del sistema per restare
limitato, un bottone mai premuto occupa spazio finche' non lo scalza uno piu'
recente, esattamente come un update_id mai piu' rivisto.
"""
from __future__ import annotations

import secrets
import threading


class StoreCapability:
    """id corto -> capability token, monouso e a capienza limitata."""

    def __init__(self, capienza: int = 2048) -> None:
        self._capienza = capienza
        self._ordine: list[str] = []
        self._token: dict[str, str] = {}
        self._lucchetto = threading.Lock()

    def registra(self, token: str) -> str:
        """Un identificativo fresco per questo token. 8 byte casuali
        base64url (~11 caratteri): abbondantemente sotto il limite di 64
        byte di Telegram anche affiancato ad altri campi del bottone."""
        identificativo = secrets.token_urlsafe(8)
        with self._lucchetto:
            self._token[identificativo] = token
            self._ordine.append(identificativo)
            if len(self._ordine) > self._capienza:
                scaduto = self._ordine.pop(0)
                self._token.pop(scaduto, None)
        return identificativo

    def preleva(self, identificativo: str) -> str | None:
        """Il token, la prima e unica volta che questo identificativo viene
        richiesto; None se non e' mai esistito, e' gia' stato prelevato o e'
        stato scalzato dalla capienza limitata."""
        with self._lucchetto:
            return self._token.pop(identificativo, None)
