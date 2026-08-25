"""Come si comporta Atlas quando i suoi file sono rotti.

Sono i test che mancavano: config.json e graph.json li scrivono anche l'utente e gli
script degli agenti, e prima di questi controlli un carattere di troppo usciva come
traceback nudo, senza dire quale file aprire e senza lasciare in piedi i comandi con
cui uscirne. Un guasto previsto deve diventare un messaggio, non uno stack.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from atlascli import install_cmd  # noqa: E402
from atlascli.errori import ErroreAtlas  # noqa: E402
from tests.test_motore import Base  # noqa: E402


class GrafoRotto(Base):
    """Il grafo e' l'unica fonte di verita' del progetto: quando non si legge, il
    motore deve dirlo, non morire."""

    def test_json_troncato_solleva_un_errore_che_nomina_il_file(self):
        self.ref.json_path.write_text('{"nodes": [', encoding="utf-8")
        with self.assertRaises(self.config.ConfigError) as caso:
            self.store.load(self.ref.json_path)
        self.assertIn("graph.json", str(caso.exception))

    def test_json_valido_ma_senza_nodi_non_e_un_grafo(self):
        self.ref.json_path.write_text('{"pippo": 1}', encoding="utf-8")
        with self.assertRaises(self.config.ConfigError) as caso:
            self.store.load(self.ref.json_path)
        self.assertIn("nodes", str(caso.exception))

    def test_json_che_non_e_un_oggetto(self):
        self.ref.json_path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(self.config.ConfigError):
            self.store.load(self.ref.json_path)

    def test_anche_le_transazioni_lo_dicono_invece_di_morire(self):
        """Le mutazioni non passano da load(): hanno un json.load() proprio dentro
        il lock, ed e' quello il percorso che usa ogni 'atlas close'."""
        self.ref.json_path.write_text("non json", encoding="utf-8")
        for apri in (self.store.transaction, self.store.read_transaction):
            with self.subTest(apri.__name__), self.assertRaises(self.config.ConfigError):
                with apri(self.ref.json_path):
                    pass

    def test_il_grafo_sano_continua_a_leggersi(self):
        """Sensibilita' al contrario: i controlli non devono rifiutare i grafi buoni."""
        self.popola()
        self.assertEqual(3, len(self.store.load(self.ref.json_path)["nodes"]))


class ConfigRotto(Base):
    def test_config_illeggibile_nomina_il_file(self):
        (self.root / "config.json").write_text("{ non json", encoding="utf-8")
        with self.assertRaises(self.config.ConfigError) as caso:
            _ = self.ws.config
        self.assertIn("config.json", str(caso.exception))


class DoctorResiste(Base):
    """Un grafo illeggibile e' la diagnosi piu' importante che doctor possa dare:
    se si fermasse li', l'unico comando fatto per capire cosa non va sarebbe anche
    l'unico che non arriva a dirlo."""

    def test_segnala_il_grafo_rotto_e_passa_al_successivo(self):
        import io, contextlib
        self.mutate.create_graph(self.ws, "secondo", "Secondo", "Un altro grafo.")
        self.ref.json_path.write_text("{ rotto", encoding="utf-8")
        uscita = io.StringIO()
        with contextlib.redirect_stdout(uscita):
            self.doctor.show_doctor(self.ws)
        testo = uscita.getvalue()
        self.assertIn("prova", testo)
        self.assertIn("graph.json", testo)


class LettureDelCliGlobale(unittest.TestCase):
    """La meta' che gestisce i progetti ha i suoi file e il suo errore."""

    def setUp(self):
        import tempfile
        from atlascli import errori
        self.errori = errori
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_json_rotto_diventa_un_errore_che_nomina_il_file(self):
        path = self.dir / "atlas.json"
        path.write_text("{ rotto", encoding="utf-8")
        with self.assertRaises(self.errori.ErroreAtlas) as caso:
            self.errori.leggi_json(path)
        self.assertIn("atlas.json", str(caso.exception))

    def test_json_valido_ma_non_oggetto(self):
        path = self.dir / "atlas.json"
        path.write_text("[1, 2]", encoding="utf-8")
        with self.assertRaises(self.errori.ErroreAtlas):
            self.errori.leggi_json(path)

    def test_un_oggetto_valido_passa(self):
        path = self.dir / "atlas.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        self.assertEqual({"a": 1}, self.errori.leggi_json(path))

    def test_la_lingua_non_blocca_l_avvio_su_un_config_rotto(self):
        """dispatch._lingua_scritta gira prima di ogni comando, anche di 'uninstall':
        se sollevasse, non resterebbe alcun modo di uscire dal guasto."""
        from atlascli import dispatch
        (self.dir / ".atlas").mkdir()
        (self.dir / ".atlas" / "config.json").write_text("{ rotto", encoding="utf-8")
        self.assertIsNone(dispatch._lingua_scritta(self.dir))

    def test_la_lingua_si_legge_quando_il_config_e_sano(self):
        from atlascli import dispatch
        (self.dir / ".atlas").mkdir()
        (self.dir / ".atlas" / "config.json").write_text('{"language": "en"}', encoding="utf-8")
        self.assertEqual("en", dispatch._lingua_scritta(self.dir))


class RiconoscimentoHook(unittest.TestCase):
    """Il gruppo SessionEnd di Atlas si riconosce dal comando, non dalla cartella.

    Cercare DIRNAME smise di funzionare quando l'hook divento' un comando: install
    ne accodava uno a ogni giro e uninstall non ne toglieva nessuno.
    """

    def gruppo(self, comando: str) -> dict:
        return {"hooks": [{"type": "command", "command": comando}]}

    def test_riconosce_la_forma_attuale(self):
        from atlascli.hook import COMANDO, nostro
        self.assertTrue(nostro(self.gruppo(COMANDO)))

    def test_riconosce_la_forma_della_0_6(self):
        from atlascli.hook import nostro
        vecchio = 'python3 "$CLAUDE_PROJECT_DIR/.atlas/hooks/session_end.py"'
        self.assertTrue(nostro(self.gruppo(vecchio)))

    def test_lascia_stare_gli_hook_di_altri(self):
        from atlascli.hook import nostro
        self.assertFalse(nostro(self.gruppo("npm run build")))
        self.assertFalse(nostro(self.gruppo("atlas-qualcosa-di-altri")))

    def test_l_elenco_aggiornato_ne_lascia_uno_solo_e_non_tocca_gli_altri(self):
        from atlascli.hook import elenco_aggiornato, nostro
        gruppi = [self.gruppo("echo mio"), self.gruppo("atlas render --all")]
        primo = elenco_aggiornato(gruppi, "msg")
        self.assertEqual(1, sum(1 for g in primo if nostro(g)))
        self.assertIn(self.gruppo("echo mio"), primo)
        self.assertEqual(primo, elenco_aggiornato(primo, "msg"), "deve essere idempotente")


class UscitaUtf8(unittest.TestCase):
    """Con l'output rediretto Python usa la codifica di sistema, che su Windows non
    sa rappresentare le frecce di 'atlas update' ne' i filetti di 'atlas how-to'."""

    class Flusso:
        def __init__(self):
            self.chiamate = []

        def reconfigure(self, **kwargs):
            self.chiamate.append(kwargs)

    def test_forza_utf8_su_stdout_e_stderr(self):
        from atlascli import main as entrypoint
        finti = (self.Flusso(), self.Flusso())
        with mock.patch.object(entrypoint.sys, "stdout", finti[0]), \
             mock.patch.object(entrypoint.sys, "stderr", finti[1]):
            entrypoint._uscita_utf8()
        for flusso in finti:
            self.assertEqual([{"encoding": "utf-8"}], flusso.chiamate)

    def test_un_flusso_che_non_si_riconfigura_non_fa_saltare_il_comando(self):
        from atlascli import main as entrypoint
        with mock.patch.object(entrypoint.sys, "stdout", object()), \
             mock.patch.object(entrypoint.sys, "stderr", object()):
            entrypoint._uscita_utf8()      # non deve sollevare


class _ProgettoVuoto(unittest.TestCase):
    """Una cartella qualsiasi, com'e' quella su cui si lancia install la prima volta."""

    def setUp(self):
        self.target = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.target, ignore_errors=True)

    def args(self, **extra):
        base = dict(dry_run=True, yes=True, no_claude_md=False, no_hooks=True,
                    graph=None, slug=None, no_registry=True)
        base.update(extra)
        return SimpleNamespace(**base)

    def installer(self, **extra) -> install_cmd.Installer:
        return install_cmd.Installer(self.target, self.args(**extra), "it")


class AnteprimaInstall(_ProgettoVuoto):
    """--dry-run e' il modo in cui si controlla un'installazione prima di farla: se
    muore proprio sul progetto pulito, l'anteprima non serve a niente. Moriva perche'
    contratto() rileggeva .atlas/CONTRACT.md, che in anteprima non viene scritto."""

    def test_l_anteprima_non_muore_e_non_scrive_niente(self):
        self.installer().contratto()
        self.assertFalse((self.target / "CLAUDE.md").exists())

    def test_fuori_dall_anteprima_il_contratto_finisce_davvero_in_claude_md(self):
        self.installer(dry_run=False).contratto()
        testo = (self.target / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(install_cmd.BEGIN, testo)
        self.assertIn(install_cmd.END, testo)
        self.assertLess(len(install_cmd.BEGIN) + len(install_cmd.END) + 200, len(testo))

    def test_no_claude_md_resta_una_rinuncia(self):
        self.installer(dry_run=False, no_claude_md=True).contratto()
        self.assertFalse((self.target / "CLAUDE.md").exists())


class ProgettoSenzaSkill(_ProgettoVuoto):
    """Lo stato in cui uninstall lascia un progetto: config.json c'e' ancora, ed e' la
    firma, mentre .atlas/skills e' stata portata via. Da li' i comandi devono reggere."""

    def test_i_documenti_si_rifanno_anche_senza_la_cartella_delle_skill(self):
        (self.target / ".atlas").mkdir()
        self.installer(dry_run=False).scrive_documenti()      # non deve sollevare
        self.assertTrue((self.target / ".atlas" / "CONTRACT.md").is_file())
        self.assertTrue((self.target / ".atlas" / "README.md").is_file())


class InstallSenzaTerminale(_ProgettoVuoto):
    """Install da uno script, da una CI o da un agente: nessuno puo' rispondere alla
    domanda sul nome del progetto, e input() usciva come EOFError nudo."""

    def setUp(self):
        super().setUp()
        (self.target / ".atlas").mkdir()

    def test_stdin_muto_diventa_una_diagnosi_che_dice_come_uscirne(self):
        inst = self.installer(dry_run=False, yes=False)
        with mock.patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(ErroreAtlas) as caso:
                inst.configura()
        self.assertIn("--yes", str(caso.exception))

    def test_con_yes_non_chiede_niente_e_prende_il_nome_della_cartella(self):
        inst = self.installer(dry_run=False)
        with mock.patch("builtins.input", side_effect=AssertionError("non deve chiedere")):
            inst.configura()
        cfg = json.loads((self.target / ".atlas" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(self.target.name, cfg["project"])


if __name__ == "__main__":
    unittest.main()
