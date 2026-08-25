"""C02: prova su due cloni veri: merge driver e lucchetto remoto.

Due cloni dello stesso progetto Atlas, due identita' e due host diversi, un bare
repo locale come remote condiviso. La prova esercita i meccanismi veri, quelli
che una prova compiacente lascerebbe stare:

  - il merge driver git scatta da solo dentro un merge reale e fonde per nodo:
    chiusure disgiunte coesistono, e un campo array dello stesso nodo cambiato
    da entrambi i lati (che un merge per righe corromperebbe coi marker git) esce
    come unione pulita;
  - un conflitto vero (stesso nodo chiuso da entrambi) esce come JSON valido con
    il campo 'conflicts', 'atlas conflicts' lo elenca e '--resolve' lo dichiara
    risolto togliendo il campo, senza marker git nel file;
  - la ref remota refs/atlas/<slug>/<id> e' la guardia fra due macchine: presa su
    una, l'altra e' rifiutata finche' la ref e' fresca; liberata sulla chiusura,
    l'altra la riprende; scaduta, il furto e' lecito e il possessore cambia;
  - senza rete le letture degradano con avviso (il rinnovo non allunga un lease
    non dimostrabile) e le mutazioni restano fail-closed.

Si usa l'eseguibile vero (dist/atlas) come sottoprocesso nei due cloni, come fa
tests/e2e.py: i moduli sorgente li coprono i test unitari, qui si prova il CLI.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "dist" / "atlas"
GITHUB_OFF = "http://127.0.0.1:1"   # il check aggiornamenti fallisce subito, non dopo 15 s


def _nome(riga: str) -> str:
    return riga.split()[-1] if riga.strip() else ""


class DueCloni(unittest.TestCase):
    def setUp(self):
        if not CLI.is_file():
            self.skipTest("manca dist/atlas: lancia prima 'python3 build.py'")
        if not shutil.which("git"):
            self.skipTest("git non disponibile")
        self.tmp = Path(tempfile.mkdtemp(prefix="atlas-due-cloni-"))
        self.registro = self.tmp / "registro.json"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        shutil.copy2(CLI, self.bin / "atlas")     # copia, non symlink: portabile anche dove
        (self.bin / "atlas").chmod(0o755)         # i symlink non si possono creare

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- primitivi ----------------------------------------------------------

    def _git(self, cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)

    def _git_env(self) -> dict:
        """L'ambiente per i comandi git che devono far scattare il driver: atlas su PATH."""
        return dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
                    ATLAS_UPDATE_BASE_URL=GITHUB_OFF)

    def _atlas(self, cwd: Path, *args: str, host: str = "", ident: str = "") -> subprocess.CompletedProcess:
        env = dict(os.environ, ATLAS_CONFIG=str(self.registro), ATLAS_UPDATE_BASE_URL=GITHUB_OFF)
        if host:
            env["ATLAS_HOST"] = host
        if ident:
            env["ATLAS_IDENTITY"] = ident
        return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd, env=env,
                              capture_output=True, text=True)

    # --- sandbox ------------------------------------------------------------

    def _set_config(self, clone: Path, ttl: int | None = None, lock_remote: str | None = None) -> None:
        """Patch chirurgica di config.json: ttl del lease e/o lock.remote."""
        cfgp = clone / ".atlas" / "config.json"
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        if ttl is not None:
            cfg.setdefault("agent", {})["lease_ttl_seconds"] = ttl
        if lock_remote is not None:
            cfg.setdefault("lock", {})["remote"] = lock_remote
        cfgp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _sandbox(self, nodi: list[str], with_lock: bool = False, ttl: int | None = None) -> SimpleNamespace:
        """Progetto seed installato, bare remote, due cloni A e B allineati.

        Il seed nasce con i nodi chiesti (tutti aperti, ramo A, senza archi) e col
        merge driver registrato: la config git e il .gitattributes viaggiano nel
        commit di base, poi ogni clone riinstalla per avere anche lui il driver nel
        proprio config git locale (quello non si clona).
        """
        seed = self.tmp / "seed"
        seed.mkdir()
        self._git(seed, "init", "-q")
        self._git(seed, "config", "user.name", "prova")
        self._git(seed, "config", "user.email", "prova@prova")
        ramo = self._git(seed, "symbolic-ref", "--short", "HEAD").stdout.strip()
        esito = self._atlas(seed, "install", str(seed), "--yes", "--graph", "demo")
        self.assertEqual(0, esito.returncode, esito.stderr)
        script = seed / ".atlas" / "scripts" / "001-nodi.py"
        corpo = "from core import mutate\n\ndef run(g):\n"
        corpo += "    mutate.add_branch(g, 'B', 'Beta', '#16a34a')\n"
        for nid in nodi:
            corpo += (f"    mutate.add_node(g, id='{nid}', title='{nid}', branch='A', "
                      f"question='q {nid}', type='task', mode='AFK')\n")
        script.write_text(corpo, encoding="utf-8")
        esito = self._atlas(seed, "exec", ".atlas/scripts/001-nodi.py")
        self.assertEqual(0, esito.returncode, esito.stderr)
        self._git(seed, "add", "-A")
        self._git(seed, "commit", "-q", "-m", "base")
        remote = self.tmp / "remote.git"
        self._git(self.tmp, "init", "-q", "--bare", str(remote))
        self._git(remote, "symbolic-ref", "HEAD", f"refs/heads/{ramo}")
        self._git(seed, "remote", "add", "origin", str(remote))
        self._git(seed, "push", "-q", "-u", "origin", ramo, env=self._git_env())
        a, b = self.tmp / "clone-A", self.tmp / "clone-B"
        self._git(self.tmp, "clone", "-q", str(remote), str(a))
        self._git(self.tmp, "clone", "-q", str(remote), str(b))
        for clone in (a, b):
            self._git(clone, "config", "user.name", "prova")
            self._git(clone, "config", "user.email", "prova@prova")
            esito = self._atlas(clone, "install", str(clone), "--yes")
            self.assertEqual(0, esito.returncode, esito.stderr)
            if with_lock or ttl is not None:
                self._set_config(clone, ttl=ttl, lock_remote=str(remote) if with_lock else None)
        grafo = next((a / ".atlas" / "graphs").glob("*/graph.json"))
        slug = grafo.parent.name
        return SimpleNamespace(A=a, B=b, remote=remote, slug=slug, ramo=ramo, tmp=self.tmp)

    def _gpath(self, clone: Path, slug: str) -> Path:
        return clone / ".atlas" / "graphs" / slug / "graph.json"

    def _commit_grafo(self, clone: Path, slug: str, msg: str) -> subprocess.CompletedProcess:
        """Commits solo graph.json: map.md e ticket sono derivati dal grafo, e un
        loro conflitto di righe non c'entra con la fusione che qui si prova."""
        rel = self._gpath(clone, slug).relative_to(clone)
        self._git(clone, "add", str(rel))
        return self._git(clone, "commit", "-q", "-m", msg)

    def _take(self, clone: Path, nid: str, host: str, ident: str) -> subprocess.CompletedProcess:
        return self._atlas(clone, "take", nid, "--identity", ident, host=host, ident=ident)

    def _scrivi_risposta(self, clone: Path, slug: str, nid: str, ans: str) -> None:
        ticket = clone / ".atlas" / "graphs" / slug / "tickets" / f"{nid}.md"
        testo = ticket.read_text(encoding="utf-8-sig")
        ticket.write_text(testo.rstrip() + f"\n\n{ans}\n", encoding="utf-8")

    def _chiudi(self, clone: Path, slug: str, nid: str, host: str, ident: str, ans: str) -> None:
        self._scrivi_risposta(clone, slug, nid, ans)
        artefatto = f".atlas/graphs/{slug}/tickets/{nid}.md"
        esito = self._atlas(clone, "close", nid, "-s", ans, "--identity", ident,
                            "--artefatti", artefatto, host=host, ident=ident)
        self.assertEqual(0, esito.returncode, esito.stderr)

    def _mutate_link(self, clone: Path, slug: str, nodo: str, dep: str) -> None:
        script = clone / ".atlas" / "scripts" / f"link-{nodo}-{dep}.py"
        script.write_text(f"from core import mutate\n\ndef run(g):\n"
                          f"    mutate.link(g, '{nodo}', '{dep}')\n", encoding="utf-8")
        esito = self._atlas(clone, "exec", f".atlas/scripts/{script.name}")
        self.assertEqual(0, esito.returncode, esito.stderr)

    def _refs(self) -> list[str]:
        """Le ref del lucchetto remoto sul remote condiviso, come le vede git."""
        esito = self._git(self.tmp / "remote.git", "for-each-ref", "refs/atlas")
        return [_nome(r) for r in esito.stdout.splitlines() if r.strip()]

    def _ref_host(self, refname: str) -> str | None:
        """L'host scritto nel token della ref: 'ATLAS-LOCK <host> <epoch>'."""
        sha = self._git(self.tmp / "remote.git", "rev-parse", refname).stdout.strip()
        msg = self._git(self.tmp / "remote.git", "show", "-s", "--format=%s", sha).stdout.strip()
        parti = msg.split()
        return parti[1] if len(parti) >= 2 else None

    # --- il merge driver in un merge reale ----------------------------------

    def test_merge_driver_fonde_le_chiusure_in_un_merge_reale(self):
        """Due cloni divergono su nodi diversi e su un campo array dello stesso
        nodo: il driver scatta da solo, entrambe le chiusure restano e l'array si
        unisce per elemento. Un merge per righe avrebbe corrotto il JSON coi
        marker git sulla riga dell'array: il test lo pretende, quindi la prova non
        e' compiacente."""
        s = self._sandbox(["M01", "M02", "M03", "M05", "M06"])

        # A: chiude M02 e aggiunge a M01 il bloccante M05
        self._take(s.A, "M02", "macchina-A", "macchina-A")
        self._chiudi(s.A, s.slug, "M02", "macchina-A", "macchina-A", "chiuso da A")
        self._mutate_link(s.A, s.slug, "M01", "M05")
        self._commit_grafo(s.A, s.slug, "A chiude M02, M01->M05")
        self._git(s.A, "push", "-q", "origin", s.ramo, env=self._git_env())

        # B: chiude M03 e aggiunge a M01 il bloccante M06
        self._take(s.B, "M03", "macchina-B", "macchina-B")
        self._chiudi(s.B, s.slug, "M03", "macchina-B", "macchina-B", "chiuso da B")
        self._mutate_link(s.B, s.slug, "M01", "M06")
        self._commit_grafo(s.B, s.slug, "B chiude M03, M01->M06")

        # il merge vero: B tira dentro il lavoro di A
        self._git(s.B, "fetch", "origin", env=self._git_env())
        merge = self._git(s.B, "merge", f"origin/{s.ramo}", env=self._git_env())
        self.assertEqual(0, merge.returncode, merge.stdout + merge.stderr)
        self.assertNotIn("CONFLICT", merge.stdout)

        # il driver era registrato nel repo dove il merge e' girato
        cfg = self._git(s.B, "config", "--get", "merge.atlas-graph.driver").stdout.strip()
        self.assertIn("atlas merge-graph", cfg)

        # il grafo fuso e' JSON valido, senza conflitti dichiarati e senza marker
        testo = self._gpath(s.B, s.slug).read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", testo)
        g = json.loads(testo)
        self.assertNotIn("conflicts", g)
        per_id = {n["id"]: n for n in g["nodes"]}
        self.assertEqual("closed", per_id["M02"]["status"])
        self.assertEqual("chiuso da A", per_id["M02"]["answer"])
        self.assertEqual("closed", per_id["M03"]["status"])
        self.assertEqual("chiuso da B", per_id["M03"]["answer"])
        self.assertEqual(["M05", "M06"], sorted(per_id["M01"]["blockedBy"]))

    def test_merge_driver_dichiara_il_conflitto_e_conflicts_lo_risolve(self):
        """Entrambi i cloni chiudono lo stesso nodo: il driver esce 1, scrive un
        JSON valido col campo 'conflicts', non lascia marker git; 'atlas conflicts'
        lo elenca e '--resolve' lo dichiara risolto togliendo il campo."""
        s = self._sandbox(["M01", "M04"])

        self._take(s.A, "M04", "macchina-A", "macchina-A")
        self._chiudi(s.A, s.slug, "M04", "macchina-A", "macchina-A", "chiuso da A")
        self._commit_grafo(s.A, s.slug, "A chiude M04")
        self._git(s.A, "push", "-q", "origin", s.ramo, env=self._git_env())

        self._take(s.B, "M04", "macchina-B", "macchina-B")
        self._chiudi(s.B, s.slug, "M04", "macchina-B", "macchina-B", "chiuso da B")
        self._commit_grafo(s.B, s.slug, "B chiude M04")

        self._git(s.B, "fetch", "origin", env=self._git_env())
        merge = self._git(s.B, "merge", f"origin/{s.ramo}", env=self._git_env())
        self.assertEqual(1, merge.returncode)
        self.assertIn("conflitto", merge.stderr.lower())

        # il working tree ha il grafo del driver: JSON valido, conflitto dichiarato
        testo = self._gpath(s.B, s.slug).read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", testo)
        g = json.loads(testo)
        conflitti = g.get("conflicts")
        self.assertTrue(conflitti)
        self.assertEqual("M04", conflitti[0]["node"])
        self.assertEqual("close", conflitti[0]["field"])

        elenco = self._atlas(s.B, "conflicts", host="macchina-B", ident="macchina-B")
        self.assertEqual(0, elenco.returncode)
        self.assertIn("M04", elenco.stdout)
        self.assertIn("close", elenco.stdout)

        risolto = self._atlas(s.B, "conflicts", "--resolve", host="macchina-B", ident="macchina-B")
        self.assertEqual(0, risolto.returncode)
        g2 = json.loads(self._gpath(s.B, s.slug).read_text(encoding="utf-8"))
        self.assertNotIn("conflicts", g2)
        self.assertEqual("closed", next(n for n in g2["nodes"] if n["id"] == "M04")["status"])

        # la risoluzione si chiude davvero: il merge si completa col nostro grafo
        rel = self._gpath(s.B, s.slug).relative_to(s.B)
        self._git(s.B, "add", str(rel))
        chiusura = self._git(s.B, "commit", "-q", "-m", "risolto: vince la chiusura locale")
        self.assertEqual(0, chiusura.returncode, chiusura.stderr)

    # --- il lucchetto remoto fra due macchine -------------------------------

    def test_lucchetto_remoto_esclude_e_consegna_fra_due_macchine(self):
        """La ref refs/atlas/<slug>/<id> e' la guardia: presa su una macchina,
        l'altra e' rifiutata finche' e' fresca; la chiusura libera la ref e
        l'altra la riprende; scaduta, il furto e' lecito e cambia possessore."""
        s = self._sandbox(["L01", "L02", "L03"], with_lock=True, ttl=3)

        # A prende L01: la ref compare col nome di A
        self.assertEqual(0, self._take(s.A, "L01", "macchina-A", "macchina-A").returncode)
        ref_l01 = f"refs/atlas/{s.slug}/L01"
        self.assertIn(ref_l01, self._refs())
        self.assertEqual("macchina-A", self._ref_host(ref_l01))

        # B prova a prendere lo stesso nodo: rifiutato, la ref e' fresca
        rifiuto = self._take(s.B, "L01", "macchina-B", "macchina-B")
        self.assertEqual(1, rifiuto.returncode)
        self.assertIn("in lavorazione", rifiuto.stderr)
        self.assertIn("macchina-A", rifiuto.stderr)

        # B prende un altro nodo, che gli appartiene
        self.assertEqual(0, self._take(s.B, "L02", "macchina-B", "macchina-B").returncode)
        self.assertIn(f"refs/atlas/{s.slug}/L02", self._refs())

        # A chiude L01: la ref si libera
        self._chiudi(s.A, s.slug, "L01", "macchina-A", "macchina-A", "fatto da A")
        self.assertNotIn(ref_l01, self._refs())

        # B chiude L02: le ref sono tutte giu'
        self._chiudi(s.B, s.slug, "L02", "macchina-B", "macchina-B", "fatto da B")
        self.assertEqual([], self._refs())

        # ora B puo' riprendere L01, che A ha mollato
        self.assertEqual(0, self._take(s.B, "L01", "macchina-B", "macchina-B").returncode)
        self.assertIn(ref_l01, self._refs())
        self.assertEqual("macchina-B", self._ref_host(ref_l01))
        # B libera la sua sessione
        self.assertEqual(0, self._atlas(s.B, "release", "L01", "--identity", "macchina-B",
                                        host="macchina-B", ident="macchina-B").returncode)

        # scadenza: A prende L03 col lease breve, aspetta che scada, B glielo ruba
        self.assertEqual(0, self._take(s.A, "L03", "macchina-A", "macchina-A").returncode)
        ref_l03 = f"refs/atlas/{s.slug}/L03"
        self.assertEqual("macchina-A", self._ref_host(ref_l03))
        time.sleep(4)   # TTL 3 s: la ref di A scade
        furto = self._take(s.B, "L03", "macchina-B", "macchina-B")
        self.assertEqual(0, furto.returncode, furto.stderr)
        self.assertEqual("macchina-B", self._ref_host(ref_l03))

    def test_senza_rete_le_letture_degradano_e_le_scritture_rifiutano(self):
        """Col remote irraggiungibile: una lettura esce con l'avviso (il rinnovo
        non allunga un lease non dimostrabile), una scrittura resta chiusa."""
        s = self._sandbox(["L01", "L02"], with_lock=True, ttl=3)
        self.assertEqual(0, self._take(s.A, "L01", "macchina-A", "macchina-A").returncode)
        time.sleep(2)   # il lease di A e' vicino alla scadenza: la lettura provera' a rinnovarlo

        rotto = str(self.tmp / "manca.git")   # remote inesistente = rete assente
        for clone in (s.A, s.B):
            self._set_config(clone, ttl=3, lock_remote=rotto)

        lettura = self._atlas(s.A, "status", host="macchina-A", ident="macchina-A")
        self.assertEqual(0, lettura.returncode, lettura.stderr)
        self.assertIn("remote non raggiungibile", lettura.stdout)

        scrittura = self._take(s.B, "L02", "macchina-B", "macchina-B")
        self.assertEqual(1, scrittura.returncode)
        self.assertIn("non è raggiungibile", scrittura.stderr)


if __name__ == "__main__":
    unittest.main()
