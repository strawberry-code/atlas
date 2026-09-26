"""closing_commit e changed_since: il commit del lavoro del nodo, che il contratto
vuole dopo close, non e' una scrittura postuma; una modifica successiva si'."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload"))

from core import gitscan  # noqa: E402

GRAFO = ".atlas/graphs/g/graph.json"


class CommitDiChiusura(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self.git("init", "-q")
        self.scrivi_grafo(None)
        self.commit("2026-01-01T10:00:00+00:00", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *argomenti, data=None):
        env = dict(self.env)
        if data:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = data
        subprocess.run(["git", *argomenti], cwd=self.root, env=env, check=True,
                       capture_output=True)

    def commit(self, data, messaggio):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", messaggio, data=data)

    def scrivi_grafo(self, chiuso):
        p = self.root / GRAFO
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"nodes": [{"id": "N1", "closedAt": chiuso}]}))

    def test_il_commit_del_lavoro_dopo_close_non_e_postumo(self):
        chiuso = "2026-01-02T10:00:00+00:00"
        (self.root / "a.md").write_text("lavoro")
        self.scrivi_grafo(chiuso)
        self.commit("2026-01-02T10:05:00+00:00", "feat(n1): lavoro e chiusura")

        base = gitscan.closing_commit(self.root, GRAFO, "N1", chiuso)
        self.assertIsNotNone(base)
        self.assertIs(gitscan.changed_since(self.root, "a.md", chiuso, base), False)
        # Senza base resta il comportamento di ripiego, che lo conta come postumo.
        self.assertIs(gitscan.changed_since(self.root, "a.md", chiuso), True)

    def test_una_modifica_dopo_il_commit_di_chiusura_resta_postuma(self):
        chiuso = "2026-01-02T10:00:00+00:00"
        (self.root / "a.md").write_text("lavoro")
        self.scrivi_grafo(chiuso)
        self.commit("2026-01-02T10:05:00+00:00", "feat(n1): lavoro e chiusura")
        (self.root / "a.md").write_text("ritocco")
        self.commit("2026-01-03T10:00:00+00:00", "fix: ritocco")

        base = gitscan.closing_commit(self.root, GRAFO, "N1", chiuso)
        self.assertIs(gitscan.changed_since(self.root, "a.md", chiuso, base), True)

    def test_chiusura_mai_committata_non_trova_base(self):
        self.assertIsNone(gitscan.closing_commit(self.root, GRAFO, "N1",
                                                 "2026-01-02T10:00:00+00:00"))


if __name__ == "__main__":
    unittest.main()
