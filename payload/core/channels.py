"""Confine provider-agnostico fra il coordinatore notifiche e un canale.

Stesso ruolo di adapters.py per Autopilot, per un dominio diverso: notify.py
decide quando una consegna e' dovuta, un canale (locale, Himalaya, Telegram,
...) sa solo come farla arrivare.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class Channel(Protocol):
    """Canale di consegna, provider-agnostico: locale, Himalaya, Telegram, ..."""

    identity: str

    def deliver(self, interaction: Mapping[str, object]) -> None: ...


class ChannelRegistryError(ValueError):
    """Identita' di canale mancante, duplicata o non configurata."""


class ChannelRegistry:
    """Registro in memoria dei canali configurati esplicitamente per il run."""

    def __init__(self, channels: Iterable[Channel] = ()) -> None:
        self._channels: dict[str, Channel] = {}
        for channel in channels:
            self.register(channel)

    def register(self, channel: Channel) -> None:
        identity = channel.identity
        if not isinstance(identity, str) or not identity or identity != identity.strip():
            raise ChannelRegistryError("channel identity must be non-empty")
        if identity in self._channels:
            raise ChannelRegistryError(f"channel identity already registered: {identity}")
        self._channels[identity] = channel

    def get(self, identity: str) -> Channel:
        try:
            return self._channels[identity]
        except KeyError:
            raise ChannelRegistryError(f"channel identity is not configured: {identity}") from None

    def identities(self) -> tuple[str, ...]:
        return tuple(sorted(self._channels))
