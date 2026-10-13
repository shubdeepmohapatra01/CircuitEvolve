#!/usr/bin/env bash
# Fetch + build Genesis (ruadapt/Genesis-CVDV-Compiler, Apache-2.0) at the pinned commit into
# third_party/genesis (no .git). Needs env `cvdv-opt` (openjdk 17 + conda-forge antlr=4.13.2).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="$(cat "$HERE/third_party/GENESIS_COMMIT")"
DST="$HERE/third_party/genesis"; TMP="$(mktemp -d)"
git clone -q https://github.com/ruadapt/Genesis-CVDV-Compiler.git "$TMP/g"
git -C "$TMP/g" checkout -q "$COMMIT"
rm -rf "$DST"; mkdir -p "$DST"; (cd "$TMP/g" && tar --exclude .git -cf - .) | (cd "$DST" && tar -xf -)
PREFIX="$(python -c 'import os,sys; print(os.path.realpath(sys.executable).rsplit("/bin/",1)[0])')"
JAR="$(find "$PREFIX" -name 'antlr4-4.13.2-complete.jar' | head -1)"
mkdir -p "$DST/generated"
(cd "$DST/grammar" && "$PREFIX/lib/jvm/bin/java" -jar "$JAR" -Dlanguage=Python3 -visitor hamiltonianDSL.g4 -o ../generated)
cp "$HERE/scripts/run_genesis.py" "$DST/run_genesis.py"
echo "Genesis $COMMIT ready at $DST"
