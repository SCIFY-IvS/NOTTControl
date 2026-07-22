#!/bin/sh
# Rebuild libmacie + zmq_server (clean + make).
# Run on nott-server from anywhere:
#   ./nottcontrol/camera/macie/rebuild_zmq_server.sh
#   # or: sh nottcontrol/camera/macie/rebuild_zmq_server.sh
#
# After building, restart zmq_server from the macie directory:
#   cd nottcontrol/camera/macie && ./macie_exe/zmq_server

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LIBMACIE="${ROOT}/libmacie"
MACIE_EXE="${ROOT}/macie_exe"

if [ -n "${LD_LIBRARY_PATH:-}" ]; then
  LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/usr/local/lib/macie_lib"
else
  LD_LIBRARY_PATH="/usr/local/lib/macie_lib"
fi
export LD_LIBRARY_PATH

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
echo "Restart with:"
echo "  cd ${ROOT} && ./macie_exe/zmq_server"
