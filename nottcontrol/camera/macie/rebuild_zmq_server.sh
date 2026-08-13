#!/bin/sh
# Rebuild libmacie + zmq_server (clean + make).
# Run on nott-server from anywhere:
#   ./nottcontrol/camera/macie/rebuild_zmq_server.sh
#   # or: sh nottcontrol/camera/macie/rebuild_zmq_server.sh
#
# After building, restart zmq_server from the macie directory with
# LD_LIBRARY_PATH set (see printed instructions below).

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LIBMACIE="${ROOT}/libmacie"
MACIE_EXE="${ROOT}/macie_exe"
MACIE_LIB_DIR=/usr/local/lib/macie_lib

# Same as the usual nott-server setup (avoid a leading ":" when unset).
#   export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib/macie_lib
case ":${LD_LIBRARY_PATH:-}:" in
  *":${MACIE_LIB_DIR}:"*) ;;
  *)
    if [ -n "${LD_LIBRARY_PATH:-}" ]; then
      LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${MACIE_LIB_DIR}"
    else
      LD_LIBRARY_PATH="${MACIE_LIB_DIR}"
    fi
    ;;
esac
export LD_LIBRARY_PATH
echo "==> LD_LIBRARY_PATH=${LD_LIBRARY_PATH}"

echo "==> Cleaning and building libmacie in ${LIBMACIE}"
make -C "${LIBMACIE}" clean
make -C "${LIBMACIE}"

echo "==> Cleaning and building zmq_server in ${MACIE_EXE}"
make -C "${MACIE_EXE}" clean
# Makefile clean does not remove zmq_server
rm -f "${MACIE_EXE}/zmq_server"
make -C "${MACIE_EXE}"

echo "==> Done: ${MACIE_EXE}/zmq_server"
ls -l "${MACIE_EXE}/zmq_server"
echo
echo "Restart with (LD_LIBRARY_PATH must be set in that shell):"
echo "  export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:${MACIE_LIB_DIR}"
echo "  cd ${ROOT} && ./macie_exe/zmq_server"
