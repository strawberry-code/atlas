"""Test di registry.py e dispatch.py: nessuno tocca ~/.config/atlas.json reale.

ATLAS_CONFIG punta sempre a un file temporaneo, impostato in setUp e tolto
in tearDown - stesso principio di isolamento di ATLAS_ROOT nei test del motore.
Allo stesso modo, ATLAS_UPDATE_BASE_URL punta a un server HTTP fittizio locale
per evitare vere chiamate di rete a GitHub.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Dalla 0.7 atlascli e il motore sono lo stesso programma: build.py li mette nello
# stesso archivio, e qui 'core' va reso importabile come lo sarebbe li' dentro.
sys.path.insert(0, str(ROOT / "payload"))

from atlascli import dispatch, install_cmd, registry  # noqa: E402
from atlascli import strings as atlascli_strings  # noqa: E402
from tests.httpfixture import Fixture  # noqa: E402


class Registry(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        os.environ["ATLAS_CONFIG"] = str(self.home / "atlas.json")
        self.progetti = Path(tempfile.mkdtemp())

    def tearDown(self):
        os.environ.pop("ATLAS_CONFIG", None)
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.progetti, ignore_errors=True)

    def _finto_progetto(self, nome: str) -> Path:
        """Un progetto e' tale se ha i suoi dati: config.json, non il motore."""
        path = self.progetti / nome
        (path / ".atlas").mkdir(parents=True)
        (path / ".atlas" / "config.json").write_text('{"project": "%s"}' % nome, encoding="utf-8")
        return path

    def test_slugify(self):
        self.assertEqual("mio-progetto", registry.slugify("Mio Progetto"))
        self.assertEqual("a-b-c", registry.slugify("a_b__c!!"))
        self.assertEqual("progetto", registry.slugify("///"))

    def test_round_trip(self):
        path = self._finto_progetto("alfa")
        slug = registry.register(path)
        self.assertEqual("alfa", slug)
        self.assertEqual(path.resolve(), registry.resolve("alfa"))

    def test_stesso_path_riusa_la_voce(self):
        path = self._finto_progetto("beta")
        registry.register(path, slug="beta")
        slug = registry.register(path)  # nessuno slug esplicito, path gia' noto
        self.assertEqual("beta", slug)
        self.assertEqual(1, len(registry.load()["projects"]))

    def test_collisione_slug_yes_rifiuta(self):
        p1, p2 = self._finto_progetto("g1"), self._finto_progetto("g2")
        registry.register(p1, slug="stesso")
        with self.assertRaises(registry.RegistryError):
            registry.register(p2, slug="stesso", yes=True)
        self.assertEqual(p1.resolve(), registry.resolve("stesso"))

    def test_collisione_slug_interattiva_annulla(self):
        p1, p2 = self._finto_progetto("g3"), self._finto_progetto("g4")
        registry.register(p1, slug="stesso")
        with self.assertRaises(registry.RegistryError):
            registry.register(p2, slug="stesso", chiedi=lambda _: "n")
        self.assertEqual(p1.resolve(), registry.resolve("stesso"))

    def test_collisione_slug_interattiva_conferma(self):
        p1, p2 = self._finto_progetto("g5"), self._finto_progetto("g6")
        registry.register(p1, slug="stesso")
        registry.register(p2, slug="stesso", chiedi=lambda _: "y")
        self.assertEqual(p2.resolve(), registry.resolve("stesso"))

    def test_prune_rimuove_path_mancanti(self):
        vivo = self._finto_progetto("vivo")
        morto = self._finto_progetto("morto")
        registry.register(vivo)
        registry.register(morto)
        shutil.rmtree(morto)
        tolti = registry.prune()
        self.assertEqual(["morto"], tolti)
        self.assertIsNone(registry.resolve("morto"))
        self.assertIsNotNone(registry.resolve("vivo"))

    def test_status_of(self):
        path = self._finto_progetto("gamma")
        self.assertEqual(registry.STATO_OK, registry.status_of(path))
        self.assertEqual(registry.STATO_MANCANTE, registry.status_of(self.progetti / "mai-esistito"))
        (path / ".atlas" / "config.json").unlink()
        self.assertEqual(registry.STATO_NON_VALIDO, registry.status_of(path))

    def test_lingua_default_globale(self):
        self.assertEqual("it", registry.language_for())
        registry.set_language("en")
        self.assertEqual("en", registry.language_for())

    def test_lingua_override_per_progetto(self):
        path = self._finto_progetto("delta")
        registry.register(path, slug="delta")
        registry.set_language("it")
        self.assertEqual("it", registry.language_for("delta"))  # eredita il default globale
        registry.set_language("en", slug="delta")
        self.assertEqual("en", registry.language_for("delta"))  # override
        self.assertEqual("it", registry.language_for())  # il default globale non cambia

    def test_lingua_su_slug_non_registrato_solleva(self):
        with self.assertRaises(registry.RegistryError):
            registry.set_language("en", slug="mai-registrato")


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        os.environ["ATLAS_CONFIG"] = str(self.home / "atlas.json")
        # Isola la rete: dispatch.main() chiama _avvisa_aggiornamento() che farebbe
        # una vera richiesta HTTP a GitHub senza questo isolamento
        self.fixture = Fixture({})
        self.fixture.start()
        os.environ["ATLAS_UPDATE_BASE_URL"] = self.fixture.base_url
        # Isola la posizione, per la stessa ragione per cui si isola il registro:
        # 'lang' senza --global agisce sul progetto sotto la cwd, e la suite gira
        # dentro il repo, che da quando Atlas e' installato su se' stesso e' un
        # progetto Atlas. Senza questo il test riscriveva il CLAUDE.md del repo e
        # ne cambiava la lingua, continuando a passare.
        self.cwd = Path.cwd()
        os.chdir(self.home)

    def tearDown(self):
        os.chdir(self.cwd)
        self.fixture.stop()
        os.environ.pop("ATLAS_UPDATE_BASE_URL", None)
        os.environ.pop("ATLAS_CONFIG", None)
        shutil.rmtree(self.home, ignore_errors=True)
        atlascli_strings.set_language("it")  # dispatch.main() muta uno stato di modulo globale

    def test_riservato_prevale_su_tutto(self):
        self.assertIn("install", dispatch.RESERVED)
        self.assertIn("update", dispatch.RESERVED)
        self.assertIn("uninstall", dispatch.RESERVED)
        self.assertIn("list", dispatch.RESERVED)
        self.assertIn("lang", dispatch.RESERVED)

    def test_lang_globale_query_e_set(self):
        self.assertEqual(0, dispatch.main(["lang", "en"]))
        self.assertEqual("en", registry.language_for())
        self.assertEqual(0, dispatch.main(["lang"]))

    def test_lang_senza_global_tocca_il_progetto_non_il_default(self):
        """La distinzione la fa il flag, non la posizione: dentro un progetto 'lang'
        cambia quel progetto e lascia stare il default della macchina."""
        progetto = self.home / "ospite"
        (progetto / ".atlas" / "skills").mkdir(parents=True)
        (progetto / ".atlas" / "config.json").write_text('{"language": "it"}', encoding="utf-8")
        os.chdir(progetto)
        self.assertEqual(0, dispatch.main(["lang", "en"]))
        dati = json.loads((progetto / ".atlas" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual("en", dati["language"])
        self.assertEqual("it", registry.language_for())   # il default globale resta fermo

    def test_progetto_qui_risale_le_cartelle(self):
        """La firma di un progetto e' config.json: i dati, non il motore, che dalla
        0.7 non abita piu' li' dentro."""
        base = Path(tempfile.mkdtemp())
        try:
            (base / ".atlas").mkdir(parents=True)
            (base / ".atlas" / "config.json").write_text("{}", encoding="utf-8")
            profonda = base / "a" / "b" / "c"
            profonda.mkdir(parents=True)
            self.assertEqual(base.resolve(), dispatch.progetto_qui(profonda))
            self.assertIsNone(dispatch.progetto_qui(Path(tempfile.gettempdir())))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_comando_sconosciuto_esce_con_errore(self):
        """Con un elenco unico se ne occupa argparse, che esce con 2 e stampa l'usage."""
        vuota = Path(tempfile.mkdtemp())
        try:
            cwd = os.getcwd()
            os.chdir(vuota)
            try:
                with self.assertRaises(SystemExit) as contesto:
                    with mock.patch("sys.stderr", io.StringIO()):
                        dispatch.main(["comando-inesistente"])
                self.assertEqual(2, contesto.exception.code)
            finally:
                os.chdir(cwd)
        finally:
            shutil.rmtree(vuota, ignore_errors=True)


class CollegaSkill(unittest.TestCase):
    """collega_skill() preferisce sempre il symlink: il fallback a copia (install_cmd.py)
    serve solo quando symlink_to non e' permesso, come su Windows senza admin/developer mode."""

    def setUp(self):
        self.target = Path(tempfile.mkdtemp())
        self.root = self.target / ".atlas"
        (self.root / "skills" / "atlas-work").mkdir(parents=True)
        (self.root / "skills" / "atlas-work" / "SKILL.md").write_text("contenuto", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.target, ignore_errors=True)

    def _installer(self) -> install_cmd.Installer:
        return install_cmd.Installer(self.target, SimpleNamespace(dry_run=False), "it")

    def test_symlink_quando_possibile(self):
        self._installer().collega_skill()
        link = self.target / ".claude" / "skills" / "atlas-work"
        self.assertTrue(link.is_symlink())

    def test_fallback_a_copia_se_symlink_fallisce(self):
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("niente symlink qui")):
            self._installer().collega_skill()
        link = self.target / ".claude" / "skills" / "atlas-work"
        self.assertFalse(link.is_symlink())
        self.assertTrue((link / install_cmd.MARCATORE).is_file())
        self.assertEqual("contenuto", (link / "SKILL.md").read_text(encoding="utf-8"))

    def test_copia_si_rigenera_al_reinstall(self):
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("niente symlink qui")):
            self._installer().collega_skill()
        (self.root / "skills" / "atlas-work" / "SKILL.md").write_text("aggiornato", encoding="utf-8")
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("niente symlink qui")):
            self._installer().collega_skill()
        link = self.target / ".claude" / "skills" / "atlas-work"
        self.assertEqual("aggiornato", (link / "SKILL.md").read_text(encoding="utf-8"))

    def test_cartella_estranea_non_simlink_viene_lasciata_stare(self):
        estranea = self.target / ".claude" / "skills" / "atlas-work"
        estranea.mkdir(parents=True)
        (estranea / "roba-mia.txt").write_text("non toccare", encoding="utf-8")
        self._installer().collega_skill()
        self.assertFalse(estranea.is_symlink())
        self.assertTrue((estranea / "roba-mia.txt").is_file())


class RifaDashboard(unittest.TestCase):
    """L'installazione rigenera le dashboard dei grafi che il progetto ha gia'.

    E' il passo che porta nei progetti una versione che ha cambiato il rendering:
    'atlas update' riallinea invocando install, e senza questo la pagina resterebbe
    quella generata dalla versione prima finche' qualcuno non tocca il grafo.
    """

    def setUp(self):
        self.target = Path(tempfile.mkdtemp())
        self.root = self.target / ".atlas"
        (self.root / "graphs").mkdir(parents=True)
        (self.root / "config.json").write_text('{"project": "prova", "language": "it"}', encoding="utf-8")

    def tearDown(self):
        os.environ.pop("ATLAS_ROOT", None)
        shutil.rmtree(self.target, ignore_errors=True)

    def _grafo(self, slug: str) -> Path:
        cartella = self.root / "graphs" / slug
        cartella.mkdir(parents=True)
        (cartella / "graph.json").write_text(json.dumps({
            "schemaVersion": 1,
            "meta": {"slug": slug, "title": "Prova", "destination": "una prova",
                     "updated": "2026-08-18", "notes": []},
            "branches": {"A": {"label": "Ramo", "color": "#4f46e5"}},
            "nodes": [], "fog": [], "outOfScope": [],
        }), encoding="utf-8")
        return cartella

    def _installa(self) -> install_cmd.Installer:
        inst = install_cmd.Installer(self.target, SimpleNamespace(dry_run=False), "it")
        inst.rifa_dashboard()
        return inst

    def test_rigenera_le_dashboard_esistenti(self):
        cartella = self._grafo("piano")
        (cartella / "dashboard.html").write_text("pagina vecchia", encoding="utf-8")
        inst = self._installa()
        self.assertNotEqual("pagina vecchia", (cartella / "dashboard.html").read_text(encoding="utf-8"))
        self.assertTrue(any("1" in riga for riga in inst.fatti))

    def test_senza_grafi_non_dice_niente(self):
        self.assertEqual([], self._installa().fatti)

    def test_un_grafo_rotto_non_fa_fallire_l_installazione(self):
        cartella = self._grafo("piano")
        (cartella / "graph.json").write_text("{ non e' json", encoding="utf-8")
        inst = self._installa()  # non solleva: l'installazione e' gia' riuscita
        self.assertEqual(1, len(inst.fatti))
        self.assertIn("render --all", inst.fatti[0])  # dice come rimediare, e nomina il motivo
        self.assertIn("graph.json", inst.fatti[0])


if __name__ == "__main__":
    unittest.main()


class Catalogo(unittest.TestCase):
    """Le chiavi t("...") del CLI globale esistono davvero nel catalogo.

    Una chiave che sparisce non rompe niente finche' nessuno passa da quella riga:
    si scopre quando un utente incontra proprio quell'errore, cioe' nel momento
    peggiore. Qui si scopre subito, e in entrambe le lingue.
    """

    def _chiavi_usate(self) -> set[str]:
        import re
        usate: set[str] = set()
        for f in (ROOT / "atlascli").glob("*.py"):
            if f.name == "strings.py":
                continue
            usate |= set(re.findall(r't\("([a-z_]+\.[a-z_]+)"', f.read_text(encoding="utf-8")))
        return usate

    def test_ogni_chiave_usata_esiste(self):
        mancanti = sorted(self._chiavi_usate() - set(atlascli_strings.STRINGS))
        self.assertEqual([], mancanti, f"chiavi usate ma assenti dal catalogo: {mancanti}")

    def test_ogni_voce_ha_entrambe_le_lingue(self):
        monche = sorted(k for k, v in atlascli_strings.STRINGS.items() if set(v) != {"it", "en"})
        self.assertEqual([], monche, f"voci senza tutte e due le lingue: {monche}")


class ImportDopoLoScambio(unittest.TestCase):
    """self_update.py non puo' avere import differiti: sostituisce l'eseguibile.

    atlas e' uno zipapp, e zipimport tiene gli offset del file che ha aperto
    all'avvio. Appena os.replace mette al suo posto un archivio diverso, ogni
    import che non sia gia' avvenuto muore con 'bad local file header', e muore
    nel punto peggiore: ad aggiornamento riuscito, dopo aver detto che era andato
    bene. E' costato un rilascio: la prova e2e pubblicava come versione nuova una
    copia identica del binario, che avendo gli stessi offset non rompeva niente.
    """

    def test_self_update_importa_tutto_prima(self):
        import ast
        sorgente = (ROOT / "atlascli" / "self_update.py").read_text(encoding="utf-8")
        albero = ast.parse(sorgente)
        differiti = [
            f"riga {nodo.lineno}"
            for funzione in ast.walk(albero)
            if isinstance(funzione, (ast.FunctionDef, ast.AsyncFunctionDef))
            for nodo in ast.walk(funzione)
            if isinstance(nodo, (ast.Import, ast.ImportFrom))
        ]
        self.assertEqual([], differiti,
                         f"import dentro una funzione di self_update.py: {differiti}")
