"""Trasporto git-refs del lucchetto remoto: l'unica rete nuova del prodotto.

Implementa RemoteLock (core.remotelock) su refs condivise refs/atlas/*, come nel
prototipo di L03: il payload della ref e' un commit orfano con messaggio
'ATLAS-LOCK <host> <expiry-epoch>'. Acquire e' un push non forzato (il CAS di git),
ruba/rinnova/rilascia usano --force-with-lease sul valore letto, e il testo
dell'errore git non si interpreta mai: gli esiti si ricavano rileggendo la ref.
La rete assente diventa Rete, mai un traceback. Il modello di fiducia e' la
cooperazione fra agenti: git non verifica il possesso alla delete, e' mutua
esclusione, non controllo accessi.
"""
from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from core.remotelock import ACQUISITO, Esito, GARA, NON_SCADUTO, NON_TUO, RETE, TENUTO

_TIMEOUT = 60   # un remote che non risponde non deve appendere il comando per sempre


def _fresca(scadenza: int | None) -> bool:
    return scadenza is None or scadenza > int(time.time())


class TrasportoRefsGit:
    """Le primitive di L03 su un remote condiviso, come le consuma il motore.

    Usa un repo di lavoro (puppet) per creare i commit dei token e per i fetch: le
    git che toccano il remote devono avere gli oggetti in un repo locale, non nella
    cwd di chi lancia atlas. Se git manca o il puppet non parte, ogni transizione
    risponde Rete.
    """

    def __init__(self, remote: str, puppet: Path | None = None):
        self._remote = remote
        self._puppet = puppet or Path(tempfile.mkdtemp(prefix="atlas-lock-"))
        if not self._init_puppet():
            self._puppet = None

    def _init_puppet(self) -> bool:
        for args in (["init", "-q", str(self._puppet)],
                     ["-C", str(self._puppet), "config", "user.name", "atlas-lock"],
                     ["-C", str(self._puppet), "config", "user.email", "lock@atlas"]):
            try:
                subprocess.run(["git", *args], check=True, capture_output=True, text=True)
            except (OSError, subprocess.CalledProcessError):
                return False
        return True

    def _git(self, *args: str, stdin: str | None = None) -> tuple[int, str]:
        """Gira git dentro il puppet. Torna (rc, stdout+stderr)."""
        if self._puppet is None:
            return 1, "puppet non inizializzato"
        try:
            proc = subprocess.run(["git", "-C", str(self._puppet), *args],
                                  input=stdin, capture_output=True, text=True, timeout=_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            return 1, "git non risponde"
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def _parsa(self, messaggio: str) -> tuple[str | None, int | None]:
        """(host, scadenza) dal messaggio del token 'ATLAS-LOCK <host> <epoch>'.
        Un token malformato vale come fresco: host noto, scadenza assente."""
        parti = messaggio.split()
        host = parti[1] if len(parti) >= 2 else None
        if len(parti) < 3:
            return (host, None)
        try:
            return (host, int(parti[2]))
        except ValueError:
            return (host, None)

    def _commit_lock(self, host: str, scadenza: int) -> str | None:
        """Crea il commit orfano col payload e ne torna la sha. Il commit punta a un
        tree reale, non all'empty tree (git non lo trasporta nel pacchetto), ed e'
        sempre nuovo: e' la proprieta' che da' a git la semantica compare-and-swap."""
        payload = f"ATLAS-LOCK {host} {scadenza}"
        rc, blob = self._git("hash-object", "-w", "--stdin", stdin=payload + "\n")
        if rc != 0:
            return None
        rc, tree = self._git("mktree", stdin=f"100644 blob {blob.strip()}\tlock\n")
        if rc != 0:
            return None
        rc, sha = self._git("commit-tree", tree.strip(), "-m", payload)
        if rc != 0:
            return None
        return sha.strip()

    def _legge(self, nome: str) -> tuple[str | None, str | None, int | None] | None:
        """Stato della ref: (sha, host, scadenza), assente = (None,)*3, None = errore."""
        rc, out = self._git("ls-remote", self._remote, f"refs/atlas/{nome}")
        if rc != 0:
            return None
        if not out.strip():
            return (None, None, None)
        sha = out.strip().split()[0]
        rc, _ = self._git("fetch", "-q", self._remote, f"refs/atlas/{nome}")
        if rc != 0:
            return None
        rc, msg = self._git("show", "-s", "--format=%s", "FETCH_HEAD")
        if rc != 0:
            return None
        host, scadenza = self._parsa(msg)
        return (sha, host, scadenza)

    def _cas(self, nome: str, atteso: str, destinazione: str | None) -> tuple[int, str]:
        """Push col lease sul valore letto (il CAS nel varco di corsa); None cancella."""
        lease = f"--force-with-lease=refs/atlas/{nome}:{atteso}"
        if destinazione is None:
            return self._git("push", lease, self._remote, f":refs/atlas/{nome}")
        return self._git("push", lease, self._remote, f"{destinazione}:refs/atlas/{nome}")

    def acquire(self, nome: str, host: str, scadenza: int) -> Esito:
        sha = self._commit_lock(host, scadenza)
        if sha is None:
            return Esito(RETE)
        rc, _ = self._git("push", self._remote, f"{sha}:refs/atlas/{nome}")
        if rc == 0:
            return Esito(ACQUISITO)
        # Push rifiutato: la ref esiste (acquire non forzato). Rileggi chi la tiene.
        stato = self._legge(nome)
        if stato is None:
            return Esito(RETE)
        if stato[0] is None:
            return Esito(GARA)
        return Esito(TENUTO, host=stato[1], scadenza=stato[2])

    def ruba(self, nome: str, host: str, scadenza: int) -> Esito:
        stato = self._legge(nome)
        if stato is None:
            return Esito(RETE)
        osha, oh_host, oh_scad = stato
        if osha is None:
            return self.acquire(nome, host, scadenza)     # nulla da rubare: e' libera
        if _fresca(oh_scad):
            return Esito(NON_SCADUTO, host=oh_host, scadenza=oh_scad)
        sha = self._commit_lock(host, scadenza)
        if sha is None:
            return Esito(RETE)
        rc, _ = self._cas(nome, osha, sha)
        return Esito(ACQUISITO) if rc == 0 else Esito(GARA)

    def rinnova(self, nome: str, host: str, scadenza: int) -> Esito:
        stato = self._legge(nome)
        if stato is None:
            return Esito(RETE)
        osha, oh_host, oh_scad = stato
        if osha is None:
            return self.acquire(nome, host, scadenza)     # la ref non c'e': riprendila
        if oh_host != host and _fresca(oh_scad):
            return Esito(NON_TUO, host=oh_host, scadenza=oh_scad)
        sha = self._commit_lock(host, scadenza)
        if sha is None:
            return Esito(RETE)
        rc, _ = self._cas(nome, osha, sha)
        return Esito(ACQUISITO) if rc == 0 else Esito(GARA)

    def rilascia(self, nome: str, host: str) -> Esito:
        stato = self._legge(nome)
        if stato is None:
            return Esito(RETE)
        osha, oh_host, oh_scad = stato
        if osha is None:
            return Esito(ACQUISITO)                       # gia' libera: idempotente
        if oh_host != host and _fresca(oh_scad):
            return Esito(NON_TUO, host=oh_host, scadenza=oh_scad)
        rc, _ = self._cas(nome, osha, None)
        return Esito(ACQUISITO) if rc == 0 else Esito(GARA)

    def stato(self, nome: str) -> Esito:
        letto = self._legge(nome)
        if letto is None:
            return Esito(RETE)
        if letto[0] is None:
            return Esito(ACQUISITO)                       # ref assente: libera
        return Esito(TENUTO, host=letto[1], scadenza=letto[2])

    def elenca(self) -> list[Esito] | Esito:
        rc, out = self._git("ls-remote", self._remote, "refs/atlas/*")
        if rc != 0:
            return Esito(RETE)
        if not out.strip():
            return []
        nomi = [riga.split()[-1].replace("refs/atlas/", "")
                for riga in out.strip().splitlines() if riga]
        rc, _ = self._git("fetch", "-q", "--prune", self._remote, "+refs/atlas/*:refs/atlas/*")
        if rc != 0:
            return Esito(RETE)
        esiti = []
        for nome in nomi:
            rc, msg = self._git("show", "-s", "--format=%s", f"refs/atlas/{nome}")
            if rc != 0:
                continue
            host, scad = self._parsa(msg)
            esiti.append(Esito(TENUTO, host=host, scadenza=scad, nome=nome))
        return esiti
