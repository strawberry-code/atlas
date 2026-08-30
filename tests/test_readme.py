"""I due README, italiano e inglese, restano in pari col CLI e fra loro.

Sono la prima cosa che uno legge e l'unica che nessun comando rigenera: un
flag rinominato o un comando nuovo li lascia indietro in silenzio, e restano
indietro finche' qualcuno non se ne accorge leggendo. Peggio ancora quando a
restare indietro e' una lingua sola, perche' allora il difetto non si vede
nemmeno confrontando il file con se stesso.

Qui non si pretende che i README siano una reference completa: si pretende che
quel che dicono esista davvero, e che lo dicano tutte e due.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))   # build_parser tira dentro i comandi del motore

from atlascli import dispatch  # noqa: E402

IT, EN = ROOT / "README.it.md", ROOT / "README.md"
CONTRACT_IT = ROOT / "payload" / "templates" / "contract.it.md"
CONTRACT_EN = ROOT / "payload" / "templates" / "contract.en.md"
README_TEMPLATE_IT = ROOT / "payload" / "templates" / "readme.it.md"
README_TEMPLATE_EN = ROOT / "payload" / "templates" / "readme.en.md"


def _dal_codice(path: Path) -> tuple[set[str], set[str]]:
    """Comandi e flag citati nei blocchi di codice, non nella prosa attorno.

    Nella prosa 'atlas' e' il nome del programma e la parola dopo e' una parola
    qualsiasi ("atlas and every project..."): confrontare quella con l'elenco
    dei comandi produrrebbe solo falsi allarmi.

    I blocchi si contano aprendo e chiudendo riga per riga invece che con una
    regex sui fence: con i fence di linguaggi diversi (powershell, python) una
    regex non-greedy scambia la chiusura di un blocco per l'apertura del
    successivo, e finisce per leggere esattamente il testo che voleva escludere.
    """
    dentro, righe = False, []
    for riga in path.read_text(encoding="utf-8").splitlines():
        if riga.startswith("```"):
            dentro = not dentro
        elif dentro:
            righe.append(riga.split("#", 1)[0])   # il commento a fine riga e' prosa, non comando
    codice = "\n".join(righe)
    return set(re.findall(r"\batlas ([a-z][a-z-]+)", codice)), set(re.findall(r"--[a-z][a-z-]+", codice))


def _titoli(path: Path) -> list[str]:
    return [cancelletti for cancelletti, _ in re.findall(r"^(#{1,4}) (.+)$",
                                                          path.read_text(encoding="utf-8"), re.M)]


class Readme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parser = dispatch.build_parser()
        sub = next(a for a in parser._actions if a.dest == "cmd" and a.choices)
        cls.comandi = set(sub.choices)
        cls.flag = {s for act in parser._actions for s in act.option_strings if s.startswith("--")}
        for sotto in sub.choices.values():
            cls.flag |= {s for act in sotto._actions for s in act.option_strings if s.startswith("--")}

    def test_ogni_comando_citato_esiste_davvero(self):
        for path in (IT, EN):
            comandi, _ = _dal_codice(path)
            with self.subTest(readme=path.name):
                self.assertEqual(set(), comandi - self.comandi,
                                 "comandi citati che il CLI non ha (piu')")

    def test_ogni_flag_citato_esiste_davvero(self):
        for path in (IT, EN):
            _, flag = _dal_codice(path)
            with self.subTest(readme=path.name):
                self.assertEqual(set(), flag - self.flag, "flag citati che il CLI non ha (piu')")

    def test_le_due_lingue_documentano_le_stesse_cose(self):
        """Aggiungere un comando o un flag in una lingua sola e' la deriva tipica:
        chi scrive tocca il file nella sua lingua e l'altro resta di una versione
        indietro, senza che nulla lo segnali."""
        comandi_it, flag_it = _dal_codice(IT)
        comandi_en, flag_en = _dal_codice(EN)
        self.assertEqual(comandi_it, comandi_en, "comandi documentati in una lingua sola")
        self.assertEqual(flag_it, flag_en, "flag documentati in una lingua sola")

    def test_le_due_lingue_hanno_la_stessa_struttura(self):
        self.assertEqual(_titoli(IT), _titoli(EN), "una sezione e' stata aggiunta o tolta a meta'")

    def test_automata_e_documentato_in_entrambi_i_readme(self):
        requisiti = {
            "README.md": ("Atlas Automata", "--parallelism", "Codex Luna", "Claude Sonnet",
                           "AdapterRegistry", "outside the sandbox", "retryable"),
            "README.it.md": ("Atlas Automata", "--parallelism", "Codex Luna", "Claude Sonnet",
                              "AdapterRegistry", "fuori sandbox", "ritentabili"),
        }
        for path in (IT, EN):
            testo = path.read_text(encoding="utf-8")
            for requisito in requisiti[path.name]:
                with self.subTest(readme=path.name, requisito=requisito):
                    self.assertIn(requisito, testo)
            self.assertNotIn("�", testo)

    def test_i_template_documentano_automata_in_entrambi_i_contratti_e_readme(self):
        requisiti = {
            CONTRACT_EN: ("Automata runs", "Codex Luna", "Claude Sonnet", "AgentAdapter",
                          "outside the sandbox", "retryable"),
            CONTRACT_IT: ("Run Automata", "Codex Luna", "Claude Sonnet", "AgentAdapter",
                          "fuori sandbox", "ritentabili"),
            README_TEMPLATE_EN: ("Automata runs", "--parallelism N", "Codex Luna", "Claude Sonnet",
                                 "AdapterRegistry", "retryable"),
            README_TEMPLATE_IT: ("Run Automata", "--parallelism N", "Codex Luna", "Claude Sonnet",
                                 "AdapterRegistry", "ritentabili"),
        }
        for path, attesi in requisiti.items():
            testo = path.read_text(encoding="utf-8")
            for atteso in attesi:
                with self.subTest(template=path.name, requisito=atteso):
                    self.assertIn(atteso, testo)
            self.assertNotIn("�", testo)


if __name__ == "__main__":
    unittest.main()
