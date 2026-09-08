#!/bin/bash
# One-shot NS-3.41 installation for a native Linux install (Ubuntu 22.04/24.04).
#
# Usage:
#   bash ns3-sim/scripts/ns3_setup.sh
#
# Run this from anywhere; it installs NS-3 under $NS3_HOME (default
# ~/ns3) and symlinks this project's ns3-sim/ directory into its
# scratch/ folder so the simulation can be built and run with ./ns3.
set -euo pipefail

NS3_VERSION="3.41"
NS3_HOME="${NS3_HOME:-$HOME/ns3}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "========================================"
echo " NS-3 ${NS3_VERSION} setup"
echo " Install dir: ${NS3_HOME}"
echo " Project dir: ${PROJECT_ROOT}"
echo "========================================"

# ── Step 1: System dependencies ──
echo "[1/7] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake ninja-build g++ ccache git \
    python3 python3-pip python3-dev python3-setuptools \
    qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools \
    gir1.2-goocanvas-2.0 gir1.2-gtk-3.0 python3-gi \
    python3-gi-cairo python3-pygraphviz graphviz \
    libsqlite3-dev libxml2-dev libxml2-utils \
    || { echo "ERROR: apt-get install failed -- check the package names above for your distro." >&2; exit 1; }

# ── Step 2: Download NS-3 ──
mkdir -p "${NS3_HOME}"
cd "${NS3_HOME}"
if [ ! -d "ns-allinone-${NS3_VERSION}" ]; then
    echo "[2/7] Downloading ns-allinone-${NS3_VERSION}..."
    curl -fSL -o "ns-allinone-${NS3_VERSION}.tar.bz2" \
        "https://www.nsnam.org/release/ns-allinone-${NS3_VERSION}.tar.bz2" \
        || { echo "ERROR: download failed." >&2; exit 1; }
    tar xjf "ns-allinone-${NS3_VERSION}.tar.bz2"
else
    echo "[2/7] ns-allinone-${NS3_VERSION} already present, skipping download."
fi

NS3_DIR="${NS3_HOME}/ns-allinone-${NS3_VERSION}/ns-${NS3_VERSION}"
cd "${NS3_DIR}"

# ── Step 3: Configure NS-3 ──
echo "[3/7] Configuring NS-3 (examples, tests, visualizer)..."
./ns3 configure --enable-examples --enable-tests --enable-visualizer \
    || { echo "ERROR: ./ns3 configure failed -- check cmake output above." >&2; exit 1; }

# ── Step 4: Build NS-3 ──
echo "[4/7] Building NS-3 (this takes a while)..."
./ns3 build -j"$(nproc)" \
    || { echo "ERROR: NS-3 build failed." >&2; exit 1; }

# ── Step 5: Build NetAnim ──
echo "[5/7] Building NetAnim..."
NETANIM_DIR="$(find "${NS3_HOME}/ns-allinone-${NS3_VERSION}" -maxdepth 1 -type d -name 'netanim-*' | head -n1)"
if [ -z "${NETANIM_DIR}" ]; then
    echo "WARNING: could not find a netanim-* directory under ns-allinone-${NS3_VERSION}; skipping NetAnim build." >&2
else
    cd "${NETANIM_DIR}"
    qmake NetAnim.pro || { echo "ERROR: qmake failed -- is qtbase5-dev installed?" >&2; exit 1; }
    make -j"$(nproc)" || { echo "ERROR: NetAnim build failed." >&2; exit 1; }
fi

# ── Step 6: Symlink this project into NS-3's scratch/ directory ──
echo "[6/7] Linking ${PROJECT_ROOT}/ns3-sim into NS-3 scratch/..."
ln -sfn "${PROJECT_ROOT}/ns3-sim" "${NS3_DIR}/scratch/aoi-scheduler"

# ── Step 7: Verify ──
echo "[7/7] Verifying build..."
cd "${NS3_DIR}"
./ns3 build scratch/aoi-scheduler/aoi-scheduler-sim \
    || { echo "ERROR: scratch build failed -- see compiler output above." >&2; exit 1; }

echo ""
echo "========================================"
echo " Setup complete."
echo " NS3_DIR=${NS3_DIR}"
echo " Try:  cd ${NS3_DIR} && ./ns3 run \"scratch/aoi-scheduler/aoi-scheduler-sim --help\""
echo "========================================"
