#!/usr/bin/env bash
# Copy a Qdrant collection from compose Qdrant (host) into the k3d cluster, then restart the API.
# Idempotent: re-running re-uploads (priority=snapshot overwrites any existing collection).
set -euo pipefail

cd "$(dirname "$0")/.."

export KUBECONFIG="${KUBECONFIG:-$PWD/infra/cluster-local/.state/kubeconfig}"
COLLECTION="${COLLECTION:-papers_c300}"
SRC="http://127.0.0.1:6333"
DST="http://127.0.0.1:16333"
NS=geoscholar
DEPLOY=deploy/geoscholar-geoscholar-api
OUT_DIR=data/snapshots

# print points_count (or fail) for a collection URL
count() {
  curl -fsS "$1/collections/$COLLECTION" |
    python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["points_count"])'
}

# 2. source check
SRC_COUNT=$(count "$SRC")
echo "source points_count: $SRC_COUNT"
[ "$SRC_COUNT" -ge 1 ] || { echo "source collection empty" >&2; exit 1; }

# 3. snapshot + download
mkdir -p "$OUT_DIR"
NAME=$(curl -fsS -X POST "$SRC/collections/$COLLECTION/snapshots" |
  python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["name"])')
SNAP="$OUT_DIR/$NAME"
curl -fsS -o "$SNAP" "$SRC/collections/$COLLECTION/snapshots/$NAME"
[ -s "$SNAP" ] || { echo "snapshot download empty: $SNAP" >&2; exit 1; }
echo "snapshot: $SNAP ($(wc -c <"$SNAP") bytes)"

# 4. port-forward
kubectl -n "$NS" port-forward svc/qdrant 16333:6333 >/dev/null 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null || true' EXIT
for _ in $(seq 30); do
  curl -fs "$DST/collections" >/dev/null 2>&1 && break
  kill -0 "$PF" 2>/dev/null || { echo "port-forward died" >&2; exit 1; }
  sleep 1
done
curl -fs "$DST/collections" >/dev/null || { echo "cluster qdrant unreachable" >&2; exit 1; }

# 5. upload (priority=snapshot replaces existing collection)
CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
  -F "snapshot=@$SNAP" \
  "$DST/collections/$COLLECTION/snapshots/upload?priority=snapshot")
[ "$CODE" = 200 ] || { echo "upload failed: HTTP $CODE" >&2; exit 1; }

# 6. verify
DST_COUNT=$(count "$DST")
echo "cluster points_count: $DST_COUNT"
[ "$DST_COUNT" = "$SRC_COUNT" ] || { echo "count mismatch: $SRC_COUNT vs $DST_COUNT" >&2; exit 1; }

# 7. restart API (BM25 built at startup)
kubectl -n "$NS" rollout restart "$DEPLOY"
kubectl -n "$NS" rollout status "$DEPLOY" --timeout=8m

# 8. summary
echo "--- done ---"
echo "source count:  $SRC_COUNT"
echo "cluster count: $DST_COUNT"
echo "snapshot:      $SNAP"
echo "rollout:       ok"
