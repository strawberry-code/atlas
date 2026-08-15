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
    # Senza interprete l'eseguibile scaricato non parte: installarlo comunque
    # lascerebbe sul disco un comando che fallisce senza dire perche'.
    echo "  atlas richiede python3 sul PATH: installalo prima di riprovare." >&2
    exit 1
fi

mkdir -p "$DIR"
TMP="$DIR/atlas.tmp.$$"
TMP_SHA="$DIR/atlas.sha.$$"
trap 'rm -f "$TMP" "$TMP_SHA"' EXIT

curl -fsSL "$URL" -o "$TMP"

# L'impronta viaggia accanto al binario nella stessa release: verificarla qui
# costa una richiesta e chiude la finestra fra 'scaricato' e 'eseguito'.
# Senza sha256sum ne' shasum non si finge una verifica: si dice che non c'e'.
ATTESO=""
if curl -fsSL "${URL}.sha256" -o "$TMP_SHA" 2>/dev/null; then
    ATTESO=$(cut -d' ' -f1 < "$TMP_SHA")
fi
if [ -z "$ATTESO" ]; then
    echo "  la release non pubblica atlas.sha256: installazione annullata." >&2
    exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
    TROVATO=$(sha256sum "$TMP" | cut -d' ' -f1)
elif command -v shasum >/dev/null 2>&1; then
    TROVATO=$(shasum -a 256 "$TMP" | cut -d' ' -f1)
else
    echo "  né sha256sum né shasum sul PATH: impossibile verificare il download," >&2
    echo "  installazione annullata. Scarica a mano da github.com/$REPO/releases" >&2
    exit 1
fi
if [ "$ATTESO" != "$TROVATO" ]; then
    echo "  sha256 non combacia (atteso $ATTESO, trovato $TROVATO):" >&2
    echo "  installazione annullata." >&2
    exit 1
fi

chmod 755 "$TMP"
mv "$TMP" "$DIR/atlas"

echo "  atlas installato in $DIR/atlas  (sha256 verificato)"

case ":$PATH:" in
    *":$DIR:"*)
        ;;
    *)
        echo "  $DIR non è nel PATH. Aggiungi questa riga al tuo shell rc:"
        echo "    export PATH=\"$DIR:\$PATH\""
        ;;
esac
