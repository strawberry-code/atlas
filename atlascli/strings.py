"""Catalogo dei messaggi del CLI globale, in italiano e inglese.

Separato dal catalogo di payload/core/strings.py: sono due distribuzioni
indipendenti, payload/ viaggia da solo dentro ogni .atlas/ e non puo' importare
da qui. Un processo 'atlas <comando>' e' one-shot: set_language() si chiama una
volta sola in dispatch.main(), letta da registry.language_for(...).
"""
from __future__ import annotations

_lingua = "it"

STRINGS: dict[str, dict[str, str]] = {
    # --- dispatch.py: parser riservato ---
    "parser.description": {"it": "Installa/aggiorna l'harness Atlas nei progetti.",
                           "en": "Installs/updates the Atlas harness in projects."},
    "help.install": {"it": "installa l'harness in un progetto", "en": "installs the harness in a project"},
    "opt.path": {"it": "cartella del progetto (default: quella corrente)",
                "en": "project folder (default: the current one)"},
    "opt.slug": {"it": "nome nel registro globale (default: nome della cartella)",
                "en": "name in the global registry (default: the folder's name)"},
    "opt.no_registry": {"it": "non registrare il progetto in ~/.config/atlas.json",
                       "en": "don't register the project in ~/.config/atlas.json"},
    "opt.yes": {"it": "niente domande, usa i default", "en": "no questions, use the defaults"},
    "opt.graph": {"it": "crea subito un grafo con questo slug", "en": "immediately creates a graph with this slug"},
    "opt.no_hooks": {"it": "non toccare .claude/settings.json", "en": "don't touch .claude/settings.json"},
    "opt.no_claude_md": {"it": "non toccare CLAUDE.md", "en": "don't touch CLAUDE.md"},
    "opt.dry_run": {"it": "dice cosa farebbe, senza farlo", "en": "says what it would do, without doing it"},
    "opt.lang": {"it": "lingua dei contenuti e delle skill di questo progetto",
                "en": "language for this project's content and skills"},
    "help.uninstall": {"it": "rimuove il motore da un progetto, lascia i dati",
                      "en": "removes the engine from a project, keeps the data"},
    "help.update": {"it": "aggiorna il CLI globale (mai i progetti)",
                   "en": "updates the global CLI (never the projects)"},
    "help.list": {"it": "progetti registrati e il loro stato", "en": "registered projects and their status"},
    "opt.prune": {"it": "rimuove dal registro le voci morte", "en": "removes dead entries from the registry"},
    "help.lang": {"it": "lingua di default per i nuovi progetti", "en": "default language for new projects"},
    "opt.lang_valore": {"it": "nuovo default globale (it o en)", "en": "new global default (it or en)"},

    # --- dispatch.py: errori/scheda ---
    "dispatch.sconosciuto": {"it": "\n  '{token}' non è un comando di atlas, né un progetto registrato "
                                   "({slug_noti}), né siamo dentro un progetto con .atlas/ installato.\n"
                                   "  Comandi globali: {comandi}\n",
                             "en": "\n  '{token}' is not an atlas command, nor a registered project "
                                   "({slug_noti}), nor are we inside a project with .atlas/ installed.\n"
                                   "  Global commands: {comandi}\n"},
    "dispatch.nessuno": {"it": "nessuno", "en": "none"},

    # --- install_cmd.py ---
    "install.python_richiesto": {"it": "  Atlas richiede Python 3.10 o superiore.",
                                 "en": "  Atlas requires Python 3.10 or later."},
    "install.posix_richiesto": {"it": "  Atlas richiede un sistema POSIX: il lock del grafo usa fcntl.",
                               "en": "  Atlas requires a POSIX system: the graph lock uses fcntl."},
    "install.scriverebbe": {"it": "scriverebbe {path}", "en": "would write {path}"},
    "install.scompatterebbe": {"it": "scompatterebbe {n} file in {dirname}/",
                              "en": "would unpack {n} files into {dirname}/"},
    "install.motore_in": {"it": "motore in {dirname}/ (versione {versione})",
                         "en": "engine in {dirname}/ (version {versione})"},
    "install.config_presente": {"it": "config.json già presente, lasciato com'era",
                               "en": "config.json already present, left as-is"},
    "install.nome_progetto": {"it": "  nome del progetto [{default}]: ", "en": "  project name [{default}]: "},
    "install.config_creato": {"it": "config.json creato per '{nome}'", "en": "config.json created for '{nome}'"},
    "install.skill_dry_run": {"it": "collegherebbe le skill in .claude/skills/",
                             "en": "would link the skills into .claude/skills/"},
    "install.skill_non_symlink": {"it": "{nome} esiste e non è un symlink: lasciato com'è",
                                 "en": "{nome} exists and is not a symlink: left as-is"},
    "install.skill_collegate": {"it": "skill collegate in .claude/skills/",
                               "en": "skills linked into .claude/skills/"},
    "install.hook_esiste": {"it": "hook SessionEnd già registrato", "en": "SessionEnd hook already registered"},
    "install.hook_status": {"it": "Aggiornamento delle dashboard Atlas", "en": "Refreshing Atlas dashboards"},
    "install.hook_registrato": {"it": "hook SessionEnd registrato, hook preesistenti intatti",
                               "en": "SessionEnd hook registered, existing hooks untouched"},
    "install.claude_md_aggiornato": {"it": "blocco Atlas in CLAUDE.md aggiornato",
                                    "en": "Atlas block in CLAUDE.md updated"},
    "install.claude_md_appeso": {"it": "contratto appeso a CLAUDE.md", "en": "contract appended to CLAUDE.md"},
    "install.claude_md_creato": {"it": "CLAUDE.md creato col contratto", "en": "CLAUDE.md created with the contract"},
    "install.gitignore_commento": {"it": "# Atlas: artefatti rigenerabili", "en": "# Atlas: regenerable artifacts"},
    "install.gitignore_righe": {"it": ".gitignore: aggiunte {n} righe", "en": ".gitignore: added {n} lines"},
    "install.registrato": {"it": "registrato come '{slug}' in ~/.config/atlas.json",
                          "en": "registered as '{slug}' in ~/.config/atlas.json"},
    "install.registro_errore": {"it": "registro globale: {errore}", "en": "global registry: {errore}"},
    "install.rimosso": {"it": "\n  Motore rimosso. Restano i tuoi dati in {dirname}/: "
                              "graphs/, scripts/, config.json.\n  Cancellali a mano se non ti servono più.\n",
                       "en": "\n  Engine removed. Your data stays in {dirname}/: "
                             "graphs/, scripts/, config.json.\n  Delete it by hand if you don't need it anymore.\n"},
    "install.riepilogo": {"it": "\n  Atlas {versione} in {target}\n", "en": "\n  Atlas {versione} in {target}\n"},
    "install.prova_con": {"it": "\n  Prova con:  {dirname}/bin/atlas doctor",
                         "en": "\n  Try:  {dirname}/bin/atlas doctor"},
    "install.primo_grafo": {"it": "  Primo grafo: {dirname}/bin/atlas new <slug> -t \"Titolo\"",
                           "en": "  First graph: {dirname}/bin/atlas new <slug> -t \"Title\""},

    # --- harness_update.py ---
    "harness.non_registrato": {"it": "\n  '{slug}' non è registrato. Registralo con "
                                     "'atlas install <path> --slug {slug}'.\n",
                              "en": "\n  '{slug}' is not registered. Register it with "
                                    "'atlas install <path> --slug {slug}'.\n"},
    "harness.non_valido": {"it": "\n  '{slug}' punta a {path} ({stato}). "
                                 "Reinstalla con 'atlas install {path} --slug {slug}'.\n",
                          "en": "\n  '{slug}' points to {path} ({stato}). "
                                "Reinstall with 'atlas install {path} --slug {slug}'.\n"},
    "harness.help_update": {"it": "aggiorna il motore di questo progetto", "en": "updates this project's engine"},
    "harness.help_path": {"it": "ripunta lo slug su questo path prima di aggiornare",
                         "en": "repoints the slug to this path before updating"},
    "harness.help_lang_valore": {"it": "nuova lingua per questo progetto (it o en)",
                                "en": "new language for this project (it or en)"},
    "harness.lang_riepilogo": {"it": "  rigenerati {n}/{totale} grafi in {lingua}",
                              "en": "  regenerated {n}/{totale} graphs in {lingua}"},
    "harness.lang_falliti": {"it": " · falliti: {elenco}", "en": " · failed: {elenco}"},

    # --- self_update.py ---
    "update.errore_rete": {"it": "\n  impossibile controllare la nuova versione: {errore}\n",
                          "en": "\n  couldn't check for a new version: {errore}\n"},
    "update.senza_tag": {"it": "\n  risposta di GitHub senza tag_name: aggiornamento annullato.\n",
                        "en": "\n  GitHub's response had no tag_name: update aborted.\n"},
    "update.gia_ultima": {"it": "\n  atlas è già alla versione più recente ({versione})\n",
                         "en": "\n  atlas is already at the latest version ({versione})\n"},
    "update.asset_assente": {"it": "\n  la release {versione} non ha un asset 'atlas': aggiornamento annullato.\n",
                           "en": "\n  release {versione} has no 'atlas' asset: update aborted.\n"},
    "update.download_vuoto": {"it": "\n  download vuoto: aggiornamento annullato.\n",
                            "en": "\n  empty download: update aborted.\n"},
    "update.sha_mismatch": {"it": "\n  sha256 non combacia (atteso {atteso}, trovato {trovato}): "
                                  "aggiornamento annullato.\n",
                           "en": "\n  sha256 mismatch (expected {atteso}, got {trovato}): update aborted.\n"},
    "update.fatto": {"it": "\n  atlas {attuale} → {ultima}  ({target})\n",
                    "en": "\n  atlas {attuale} → {ultima}  ({target})\n"},

    # --- list_cmd.py ---
    "list.prune_fatto": {"it": "\n  rimossi dal registro: {elenco}\n", "en": "\n  removed from the registry: {elenco}\n"},
    "list.prune_niente": {"it": "\n  nessuna voce morta da rimuovere\n", "en": "\n  no dead entries to remove\n"},
    "list.vuoto": {"it": "\n  nessun progetto registrato. Installa con 'atlas install <path>'.\n",
                  "en": "\n  no registered projects. Install with 'atlas install <path>'.\n"},
    "list.scheda": {"it": "\n  {slug}\n  path      {path}\n  stato     {stato}\n  versione  {versione}\n\n"
                          "  Aggiorna con: atlas {slug} update\n",
                    "en": "\n  {slug}\n  path      {path}\n  status    {stato}\n  version   {versione}\n\n"
                          "  Update with: atlas {slug} update\n"},

    # --- registry.py ---
    "registry.slug_occupato": {"it": "'{slug}' è già registrato per {path}: usa --slug per un nome diverso",
                              "en": "'{slug}' is already registered for {path}: use --slug for a different name"},
    "registry.conferma_prompt": {"it": "  '{slug}' è già registrato per {path}. Sovrascrivere con {nuovo}? [y/N] ",
                                "en": "  '{slug}' is already registered for {path}. Overwrite with {nuovo}? [y/N] "},
    "registry.annullata": {"it": "registrazione annullata", "en": "registration cancelled"},
    "registry.slug_senza_progetto": {"it": "'{slug}' non è registrato: nessun progetto a cui applicare la lingua",
                                    "en": "'{slug}' is not registered: no project to apply the language to"},
}


def set_language(lingua: str) -> None:
    global _lingua
    _lingua = lingua if lingua in ("it", "en") else "it"


def current() -> str:
    return _lingua


def t(key: str, **kwargs) -> str:
    return STRINGS[key][_lingua].format(**kwargs)
