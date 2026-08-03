#!/bin/sh
# Installa il CLI globale di Atlas: curl -fsSL <raw-url>/install.sh | sh
#
# Nessun parsing JSON in shell: l'URL "releases/latest/download/<asset>" di GitHub
# risolve sempre all'asset dell'ultima release, senza passare dall'API.
# ATLAS_INSTALL_DIR/ATLAS_INSTALL_URL sono override per i test (tests/test_install_sh.py),
# non per l'uso normale.
set -eu

REPO="strawberry-code/atlas"
DIR="${ATLAS_INSTALL_DIR:-$HOME/.local/bin}"
URL="${ATLAS_INSTALL_URL:-https://github.com/$REPO/releases/latest/download/atlas}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "  atlas richiede python3 sul PATH: installalo prima di riprovare." >&2
fi

mkdir -p "$DIR"
TMP="$DIR/atlas.tmp.$$"
trap 'rm -f "$TMP"' EXIT

curl -fsSL "$URL" -o "$TMP"
chmod 755 "$TMP"
mv "$TMP" "$DIR/atlas"

echo "  atlas installato in $DIR/atlas"

case ":$PATH:" in
    *":$DIR:"*)
        ;;
    *)
        echo "  $DIR non è nel PATH. Aggiungi questa riga al tuo shell rc:"
        echo "    export PATH=\"$DIR:\$PATH\""
        ;;
esac
