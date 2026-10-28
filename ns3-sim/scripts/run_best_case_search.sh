#!/usr/bin/env bash
# Best-case regime search (docs/BEST_CASE_SEARCH.md).
# Usage: run_best_case_search.sh <stage> "<config ids>" "<seeds>"   e.g.  select "G01 G02" "300 301 302 303 304"
# Results: results/ns3_best_case_search/<stage>/<config>/<policy>/seed<N>/log.csv  (main campaign untouched)
set -euo pipefail
STAGE="$1"; IDS="$2"; SEEDS="$3"
NS3_DIR="${NS3_DIR:-$(ls -d "$HOME"/Downloads/ns-allinone-*/ns-3.* 2>/dev/null | tail -n1 || true)}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="${PROJECT_ROOT}/results/ns3_best_case_search/${STAGE}"
GRID="${PROJECT_ROOT}/ns3-sim/scripts/best_case_grid.tsv"
ART="${PROJECT_ROOT}/deploy/artifacts"
N_CORES="${N_CORES:-$(nproc 2>/dev/null || echo 4)}"
BASE="--slotDuration=0.1 --simTime=300"
JOB="$(mktemp)"; trap 'rm -f "$JOB"' EXIT
for id in $IDS; do
    flags="$(grep -P "^${id}\t" "$GRID" | cut -f2)"
    [ -n "$flags" ] || { echo "unknown config $id" >&2; exit 1; }
    for s in $SEEDS; do
        for pol in cag fpq rr; do
            o="$ROOT/$id/$pol/seed$s"; mkdir -p "$o"
            echo "--scheduler=$pol --policyId=$pol --seed=$s $BASE $flags --csvOutput=$o/log.csv" >> "$JOB"
        done
        for d in 0 1 2 3 4; do
            o="$ROOT/$id/dqn_seed$d/seed$s"; mkdir -p "$o"
            echo "--scheduler=dqn --policyFile=$ART/dqn_seed$d.txt --policyId=dqn_seed$d --seed=$s $BASE $flags --csvOutput=$o/log.csv" >> "$JOB"
        done
    done
done
SIM_BIN="$(ls "$NS3_DIR"/build/scratch/aoi-scheduler/ns3*-aoi-scheduler-sim-* | head -n1)"; export SIM_BIN
echo "$(wc -l < "$JOB") runs"
xargs -P "$N_CORES" -I{} bash -c '"$SIM_BIN" --enableNetAnim=false {} > /dev/null 2>&1 || echo "[FAILED] {}"' < "$JOB"
echo "done: $(find "$ROOT" -name log.csv | wc -l) logs under $ROOT"
