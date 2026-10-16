#!/bin/zsh
# Deploy DoughSight IQ to the DEFAULT workspace.
#   zsh scripts/deploy.sh            (build frontend, sync, deploy)
#   SKIP_BUILD=1 zsh scripts/deploy.sh
# Secrets live in config.local.env (gitignored) and are rendered into the
# workspace copy of app.yaml only.
set -euo pipefail
cd "$(dirname "$0")/.."

PROFILE=${PROFILE:-DEFAULT}
APP=${APP:-doughsight-iq}
WS=${WS:-/Workspace/Users/jonathan.whiteley@databricks.com/apps/doughsight-iq}

[[ -f config.local.env ]] || { echo "config.local.env missing (see app.yaml placeholders)"; exit 1; }
set -a; source config.local.env; set +a

if [[ -z "${SKIP_BUILD:-}" ]]; then
  (cd frontend && npm run build)
fi

echo "== sync source"
databricks sync --full . "$WS" --profile "$PROFILE" | tail -2

echo "== render app.yaml"
tmp=$(mktemp -d)
sed "s|{{TICKETMASTER_API_KEY}}|${TICKETMASTER_API_KEY}|" app.yaml > "$tmp/app.yaml"
grep -q '{{' "$tmp/app.yaml" && { echo "unfilled placeholder in app.yaml"; exit 1; }
databricks workspace import "$WS/app.yaml" --file "$tmp/app.yaml" --format AUTO --overwrite --profile "$PROFILE"
rm -rf "$tmp"

echo "== frontend dist (sync skips it via .gitignore)"
databricks workspace delete "$WS/frontend/dist" --recursive --profile "$PROFILE" 2>/dev/null || true
databricks workspace import-dir frontend/dist "$WS/frontend/dist" --overwrite --profile "$PROFILE" | tail -1

echo "== prune Node sources (auto Node build times out) and dev-only files"
for f in frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json \
         frontend/vite.config.ts frontend/tailwind.config.js frontend/postcss.config.js frontend/src tests docs config.local.env; do
  databricks workspace delete "$WS/$f" --recursive --profile "$PROFILE" 2>/dev/null && echo "  rm $f" || true
done

echo "== deploy"
databricks apps deploy "$APP" --source-code-path "$WS" --profile "$PROFILE" -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['status'])"
