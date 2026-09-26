#!/usr/bin/env bash
# Run the identifier check before every push from this clone.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
cat > .git/hooks/pre-push <<'HOOK'
#!/usr/bin/env bash
scripts/check-identifiers.sh --self-test >/dev/null || { echo "identifier check is broken"; exit 1; }
scripts/check-identifiers.sh
HOOK
chmod +x .git/hooks/pre-push
echo "pre-push hook installed"
