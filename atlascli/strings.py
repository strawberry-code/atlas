"""Catalogo dei messaggi del CLI globale, in italiano e inglese.

Separato dal catalogo del motore (payload/core/strings_*.py) anche ora che viaggiano
nello stesso eseguibile: sono due elenchi con due autori e due ritmi di modifica, e
tenerli distinti evita che un rename di la' rompa un messaggio di qua. Le due lingue
si allineano all'avvio, in dispatch._allinea_lingua().
"""
from __future__ import annotations

_lingua = "it"

STRINGS: dict[str, dict[str, str]] = {
    # --- dispatch.py: parser riservato ---
    "parser.description": {"it": "Atlas: installa l'harness nei progetti e ne lavora i grafi.",
                           "en": "Atlas: installs the harness in projects and works their graphs."},
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
    "help.uninstall": {"it": "toglie Atlas da un progetto, lascia i dati",
                      "en": "removes Atlas from a project, keeps the data"},
    "help.update": {"it": "aggiorna atlas stesso all'ultima versione",
                   "en": "updates atlas itself to the latest version"},
    "help.list": {"it": "progetti registrati e il loro stato", "en": "registered projects and their status"},
    "opt.prune": {"it": "rimuove dal registro le voci morte", "en": "removes dead entries from the registry"},
    "help.lang": {"it": "lingua dei contenuti di questo progetto", "en": "content language of this project"},
    "opt.lang_valore": {"it": "lingua da usare (it o en)", "en": "language to use (it or en)"},
    "parser.epilog": {"it": "I primi cinque comandi valgono ovunque; gli altri vogliono un progetto\n"
                            "Atlas sotto la cartella corrente, e lo trovano da soli.\n\n"
                            "  atlas how-to      il briefing completo per chi arriva adesso\n"
                            "  atlas list        i progetti registrati su questa macchina\n"
                            "  atlas render --all   rigenera i grafi di questo progetto",
                      "en": "The first five commands work anywhere; the others need an Atlas\n"
                            "project under the current folder, and find it on their own.\n\n"
                            "  atlas how-to      the full briefing for whoever just arrived\n"
                            "  atlas list        the projects registered on this machine\n"
                            "  atlas render --all   regenerates this project's graphs"},

    # --- install_cmd.py ---
    "install.python_richiesto": {"it": "  Atlas richiede Python 3.10 o superiore.",
                                 "en": "  Atlas requires Python 3.10 or later."},
    "install.scriverebbe": {"it": "scriverebbe {path}", "en": "would write {path}"},
    "install.scompatterebbe": {"it": "scompatterebbe {n} file in {dirname}/",
                              "en": "would unpack {n} files into {dirname}/"},
    "install.motore_in": {"it": "dati del progetto in {dirname}/, motore in atlas {versione}",
                         "en": "project data in {dirname}/, engine in atlas {versione}"},
    "opt.list_slug": {"it": "scheda di un progetto registrato", "en": "card of one registered project"},
    "opt.lang_globale": {"it": "cambia il default dei progetti futuri invece di questo",
                         "en": "change the default for future projects instead of this one"},
    "opt.graph_attivo": {"it": "grafo su cui lavorare, se il progetto ne ha piu' di uno",
                         "en": "graph to work on, if the project has more than one"},
    "install.lingua_progetto": {"it": "lingua del progetto: {lingua}", "en": "project language: {lingua}"},
    "install.residui_rimossi": {"it": "rimossi dalla versione precedente: {elenco}",
                                "en": "removed from the previous version: {elenco}"},
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
    "install.prova_con": {"it": "\n  Prova con:  atlas doctor",
                         "en": "\n  Try:  atlas doctor"},
    "install.primo_grafo": {"it": "  Primo grafo: atlas new <slug> -t \"Titolo\"",
                           "en": "  First graph: atlas new <slug> -t \"Title\""},

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
    "update.sha_assente": {"it": "\n  la release {versione} non pubblica 'atlas.sha256': senza impronta "
                                 "non si sa cosa si sta installando, aggiornamento annullato.\n",
                          "en": "\n  release {versione} publishes no 'atlas.sha256': without a checksum "
                                "there is no telling what would be installed, update aborted.\n"},
    "update.sha_illeggibile": {"it": "\n  l'impronta pubblicata non è uno sha256 leggibile: "
                                     "aggiornamento annullato.\n",
                              "en": "\n  the published checksum is not a readable sha256: update aborted.\n"},
    "update.url_non_sicuro": {"it": "\n  la release rimanda a un indirizzo non cifrato ({url}): "
                                    "aggiornamento annullato.\n",
                             "en": "\n  the release points at a plaintext address ({url}): update aborted.\n"},
    "update.troppo_grande": {"it": "\n  il download supera i {tetto} MB previsti: aggiornamento annullato.\n",
                            "en": "\n  the download exceeds the expected {tetto} MB: update aborted.\n"},
    "update.fatto": {"it": "\n  atlas {attuale} → {ultima}  ({target})\n",
                    "en": "\n  atlas {attuale} → {ultima}  ({target})\n"},
    "update.riallinea": {"it": "  skill, contratto e README dei progetti restano quelli della versione "
                               "precedente: {n} progetti registrati si riallineano con 'atlas install <path>'.",
                        "en": "  each project's skills, contract and README stay at the previous version: "
                              "{n} registered projects realign with 'atlas install <path>'."},
    "update.riallinea_riga": {"it": "    {slug}", "en": "    {slug}"},
    "update.riallinea_altri": {"it": "    e altri {n}", "en": "    and {n} more"},
    "update.disponibile":{"it": "\n  è disponibile atlas {nuova} (hai {attuale}): esegui 'atlas update' per aggiornare\n",
                          "en": "\n  atlas {nuova} is available (you have {attuale}): run 'atlas update' to upgrade\n"},

    # --- list_cmd.py ---
    "list.prune_fatto": {"it": "\n  rimossi dal registro: {elenco}\n", "en": "\n  removed from the registry: {elenco}\n"},
    "list.prune_niente": {"it": "\n  nessuna voce morta da rimuovere\n", "en": "\n  no dead entries to remove\n"},
    "list.vuoto": {"it": "\n  nessun progetto registrato. Installa con 'atlas install <path>'.\n",
                  "en": "\n  no registered projects. Install with 'atlas install <path>'.\n"},
    "list.slug_ignoto": {"it": "\n  nessun progetto registrato come '{slug}'. Ci sono: {elenco}\n",
                        "en": "\n  no project registered as '{slug}'. Available: {elenco}\n"},
    "list.nessuno": {"it": "nessuno", "en": "none"},
    "list.scheda": {"it": "\n  {slug}\n  path      {path}\n  stato     {stato}\n\n"
                          "  I comandi del grafo si danno da dentro il progetto.\n",
                    "en": "\n  {slug}\n  path      {path}\n  status    {stato}\n\n"
                          "  Graph commands are given from inside the project.\n"},

    # --- errori.py ---
    "errore.config_rotto": {"it": "{path} non è JSON valido ({dettaglio}).\n"
                                  "  Correggilo a mano, oppure cancellalo e rilancia 'atlas install'.",
                            "en": "{path} is not valid JSON ({dettaglio}).\n"
                                  "  Fix it by hand, or delete it and run 'atlas install' again."},
    "errore.registro_rotto": {"it": "{path} non è JSON valido ({dettaglio}).\n"
                                    "  Correggilo o cancellalo, perché è solo l'elenco dei progetti "
                                    "e si ricostruisce reinstallandoli.",
                              "en": "{path} is not valid JSON ({dettaglio}).\n"
                                    "  Fix it or delete it, since it is only the list of projects "
                                    "and it rebuilds by reinstalling them."},
    "errore.settings_rotto": {"it": "{path} non è JSON valido ({dettaglio}).\n"
                                    "  È un file di Claude Code, non di Atlas: correggilo tu, "
                                    "oppure installa con --no-hooks.",
                              "en": "{path} is not valid JSON ({dettaglio}).\n"
                                    "  It belongs to Claude Code, not to Atlas: fix it yourself, "
                                    "or install with --no-hooks."},
    "errore.non_oggetto": {"it": "il contenuto non è un oggetto JSON",
                           "en": "the content is not a JSON object"},

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
