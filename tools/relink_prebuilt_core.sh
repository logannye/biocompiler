#!/bin/sh
# Internal release companion recipe. Execute in a fresh, hosted/source build
# environment with the retained sources; replacement GMP archive/header are
# explicit arguments. No original binary fingerprint is required of a relink.
set -eu
if [ "$#" -ne 4 ]; then
  echo 'usage: relink_prebuilt_core.sh CHECKOUT GMP_ARCHIVE GMP_HEADER GMP_VERSION' >&2
  exit 2
fi
checkout=$1
archive=$2
header=$3
version=$4
cd "$checkout"
python3 - "$archive" "$header" "$version" <<'PY'
from pathlib import Path
import sys
from tools.prepare_static_gmp import prepare
prepare(archive=Path(sys.argv[1]).resolve(),header=Path(sys.argv[2]).resolve(),
        version=sys.argv[3],output=Path('relink-gmp'))
PY
export PKG_CONFIG_PATH="$checkout/relink-gmp"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"
export PKG_CONFIG_ALLOW_SYSTEM_CFLAGS=1
export PKG_CONFIG_ALLOW_SYSTEM_LIBS=1
unset PKG_CONFIG_SYSROOT_DIR
opam reinstall zarith.1.14 --yes
opam exec -- dune build --root core bin/core/main.exe bin/verify/main.exe
# This creates new bytes. The complete independent test/release gates must run
# again before those bytes can carry this project's acceptance claims.
