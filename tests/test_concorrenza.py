"""Cosa regge quando piu' agenti scrivono insieme, e quando uno muore a meta'.

Tre guasti distinti, tre difese distinte, e ognuna qui ha la sua prova:
  - due processi che scrivono insieme      -> il lock sul file dedicato
  - uno che parte da uno stato vecchio     -> la rilettura dentro la transazione
  - uno ucciso mentre riscrive il grafo    -> temporaneo piu' os.replace
Piu' la quarta, che nessuna delle tre puo' dare: accorgersi che il nodo e' cambiato
dopo la presa, cioe' che la risposta in arrivo e' stata decisa su un'altra premessa.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from tests.test_motore import Base  # noqa: E402

AGENTI, GIRI = 4, 25

FIGLIO = """
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ["ATLAS_ROOT"])
from core import store
percorso, etichetta, giri = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
for i in range(giri):
    with store.transaction(percorso) as data:
        data["fog"].append(f"{etichetta}-{i}")
"""


class Interrotto(Exception):
    """Il processo che muore mentre sta scrivendo."""


class MezzaScrittura:
    """Un file che scrive solo una frazione del testo e poi muore.

    Serve un oggetto intero e non un monkeypatch di write: TextIOWrapper e' un tipo
    immutabile e non si lascia riscrivere il metodo.
    """

    def __init__(self, vero, frazione: float):
        self.vero, self.frazione = vero, frazione

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.vero.close()
        return False

    def write(self, testo: str) -> int:
        scritti = self.vero.write(testo[:int(len(testo) * self.frazione)])
        raise Interrotto()

    def flush(self):
        self.vero.flush()

    def fileno(self):
        return self.vero.fileno()


class ScritturaAtomica(Base):
    """Il grafo sul disco e' sempre uno stato intero: quello di prima o quello di dopo.

    La versione precedente riscriveva il file vivo con seek+write+truncate. Interrotta
    a meta' lasciava due esiti, e il secondo era il peggiore: un graph.json illeggibile,
    oppure valido con dentro uno stato mai esistito, per esempio 299 nodi dove ce
    n'erano 300 e ne dovevano restare 5.
    """

    def scrivi_e_muori(self, frazione: float) -> None:
        vero_open = Path.open

        def apri(self_path, *args, **kwargs):
            handle = vero_open(self_path, *args, **kwargs)
            if self_path.name.endswith(".tmp"):
                return MezzaScrittura(handle, frazione)
            return handle

        with mock.patch.object(Path, "open", apri), self.assertRaises(Interrotto):
            with self.store.transaction(self.ref.json_path) as data:
                data["nodes"] = data["nodes"][:1]
                data["meta"]["title"] = "un titolo molto piu' lungo di quello di prima"

    def test_interrotto_a_ogni_frazione_il_grafo_resta_quello_di_prima(self):
        self.popola()
        prima = self.ref.json_path.read_text(encoding="utf-8")
        for decimo in range(1, 10):
            with self.subTest(frazione=decimo / 10):
                self.scrivi_e_muori(decimo / 10)
                self.assertEqual(prima, self.ref.json_path.read_text(encoding="utf-8"))
                self.assertEqual(3, len(self.store.load(self.ref.json_path)["nodes"]))

    def test_il_temporaneo_non_e_il_grafo_e_non_si_accumula(self):
        """Il mezzo scritto finisce in un file a parte, che la prima scrittura
        riuscita si porta via: il nome e' fisso, e sotto lock scrive uno solo."""
        self.popola()
        self.scrivi_e_muori(0.5)
        rimasti = list(self.ref.json_path.parent.glob("*.tmp"))
        self.assertEqual(1, len(rimasti))
        self.assertNotEqual(self.ref.json_path, rimasti[0])
        with self.store.transaction(self.ref.json_path) as data:
            data["fog"].append("il giro dopo")
        self.assertEqual([], list(self.ref.json_path.parent.glob("*.tmp")))

    def test_la_scrittura_riuscita_e_un_solo_replace(self):
        self.popola()
        with mock.patch.object(self.store.os, "replace", wraps=os.replace) as spia:
            with self.store.transaction(self.ref.json_path) as data:
                data["fog"].append("una riga")
        self.assertEqual(1, spia.call_count)


class LockFraProcessi(Base):
    """Quattro processi veri che martellano lo stesso grafo: nessuna scrittura persa.

    E' la prova che il lock protegge ancora dopo essere stato spostato dal descrittore
    di graph.json a un file dedicato, che era il passaggio necessario perche' os.replace
    non scavalcasse l'esclusione sostituendo l'inode sotto chi lo teneva.
    """

    def test_nessuna_scrittura_persa(self):
        self.popola()
        ambiente = dict(os.environ, ATLAS_ROOT=str(self.root))
        processi = [subprocess.Popen(
            [sys.executable, "-c", FIGLIO, str(self.ref.json_path), f"a{i}", str(GIRI)],
            env=ambiente, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for i in range(AGENTI)]
        for processo in processi:
            _, errore = processo.communicate(timeout=120)
            self.assertEqual(0, processo.returncode, errore.decode())
        righe = self.store.load(self.ref.json_path)["fog"]
        self.assertEqual(AGENTI * GIRI, len(righe))
        self.assertEqual(AGENTI * GIRI, len(set(righe)))

    def test_il_file_di_lock_non_e_il_grafo(self):
        with self.store.transaction(self.ref.json_path):
            pass
        lock = self.store._path_lock(self.ref.json_path)
        self.assertTrue(lock.is_file())
        self.assertNotEqual(lock, self.ref.json_path)


class PremessaScaduta(Base):
    """L'impronta presa al claim e riverificata alla chiusura.

    Il lock impedisce le scritture sovrapposte e la rilettura impedisce di partire da
    uno stato vecchio, ma nessuno dei due sa cosa l'agente aveva letto quando ha
    deciso cosa scrivere.
    """

    def prendi(self, node_id: str = "F01") -> dict:
        self.popola()
        return self.claims.claim(self.ref, node_id)

    def altri_toccano(self, node_id: str = "F01") -> None:
        with self.store.transaction(self.ref.json_path) as data:
            self.model.node_of(data, node_id)["question"] = "la domanda e' cambiata"

    def chiudi(self, node_id: str = "F01", **kwargs):
        with mock.patch.object(self.docs, "answer_written", return_value=True):
            return self.claims.close(self.ref, node_id, "sintesi", **kwargs)

    def test_il_claim_registra_l_impronta(self):
        nodo = self.prendi()
        self.assertEqual(self.model.fingerprint(nodo), nodo["claim"]["fingerprint"])

    def test_chiudere_un_nodo_intatto_funziona(self):
        self.prendi()
        nodo, _ = self.chiudi()
        self.assertEqual("closed", nodo["status"])

    def test_chiudere_un_nodo_cambiato_sotto_le_mani_viene_rifiutato(self):
        self.prendi()
        self.altri_toccano()
        with self.assertRaises(self.store.StateError) as caso:
            self.chiudi()
        self.assertIn("F01", str(caso.exception))

    def test_force_chiude_comunque(self):
        self.prendi()
        self.altri_toccano()
        nodo, _ = self.chiudi(force=True)
        self.assertEqual("closed", nodo["status"])

    def test_un_claim_senza_impronta_non_blocca_la_chiusura(self):
        """Retrocompatibilita': i claim presi prima della 0.7.0 non ce l'hanno."""
        self.prendi()
        with self.store.transaction(self.ref.json_path) as data:
            self.model.node_of(data, "F01")["claim"].pop("fingerprint")
        self.altri_toccano()
        nodo, _ = self.chiudi()
        self.assertEqual("closed", nodo["status"])

    def test_il_battito_non_invalida_l_impronta(self):
        """Riprendere un nodo gia' proprio aggiorna l'heartbeat: il claim cambia, il
        nodo no, e l'impronta lo esclude apposta."""
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "test-session"}):
            impronta = self.prendi()["claim"]["fingerprint"]
            self.assertEqual(impronta, self.claims.claim(self.ref, "F01")["claim"]["fingerprint"])
            nodo, _ = self.chiudi()
        self.assertEqual("closed", nodo["status"])


@unittest.skipIf(sys.platform == "win32", "flock non c'e' su Windows")
class GitFuoriDalLock(Base):
    """I due processi git della deduzione artefatti girano a lock libero.

    Su questo repo costano 24 ms, quattro volte la scrittura del grafo, e su un
    monorepo diventano secondi in cui ogni altro agente resta in coda.
    """

    def test_la_deduzione_non_tiene_il_grafo_occupato(self):
        import fcntl
        self.popola()
        self.claims.claim(self.ref, "F01")
        lock = self.store._path_lock(self.ref.json_path)
        libero = []

        def spia(root, since=None):
            with lock.open("r+b") as fh:
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    libero.append(True)
                    fcntl.flock(fh, fcntl.LOCK_UN)
                except OSError:
                    libero.append(False)
            return []

        with mock.patch.object(self.claims.gitscan, "touched", spia), \
             mock.patch.object(self.docs, "answer_written", return_value=True):
            self.claims.close(self.ref, "F01", "sintesi")
        self.assertEqual([True], libero, "git e' stato chiamato con il lock in mano")


if __name__ == "__main__":
    unittest.main()
