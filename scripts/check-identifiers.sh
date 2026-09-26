#!/usr/bin/env bash
# Fail if any tracked file contains something that identifies a real account,
# profile, employer, or person. Runs in CI on every push and pull request, and
# as a local pre-push hook (see scripts/install-hooks.sh).
#
# Usage: scripts/check-identifiers.sh            # scan tracked files
#        scripts/check-identifiers.sh --self-test # prove the scan can fail
set -uo pipefail

# One pattern per line. Extended regex, matched case-insensitively.
PATTERNS=(
  '\b[0-9]{12}\b'                  # AWS account ID (placeholders allowed below)
  'arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]{12}:'
  'AWSReservedSSO_'                # SSO role names
  'AWS_PROFILE=[a-z]'              # a real profile name baked into a script
  '--profile [a-z]'
  'op://'                          # secret store paths
  '\bncino\b'
  '\bgap-dev\b|\bbos-[a-z]'
  '\byspoc'
  'Owner,Value='
  '@[a-z0-9-]+\.(com|io|org)\b'    # email addresses (example.* allowed below)
  '(AKIA|ASIA)[A-Z0-9]{16}'        # AWS access key IDs
  'Bearer [A-Za-z0-9_\-]{12,}'
  '\bfw_[A-Za-z0-9]{12,}'
)
# Lines matching this are allowed even if a pattern above hits.
ALLOW='123456789012|111122223333|@example\.(com|org)|@acme-support\.example|dana\.backup@gmail\.com|--profile <|AWS_PROFILE=<|AWS_PROFILE="\$\{'

HITS=0
scan() {
  local files=("$@")
  HITS=0
  for p in "${PATTERNS[@]}"; do
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      if ! printf '%s' "$line" | grep -qE -- "$ALLOW"; then
        echo "IDENTIFIER: $p :: ${line:0:200}"
        HITS=$((HITS + 1))
      fi
    done < <(grep -nHiE -- "$p" "${files[@]}" 2>/dev/null)
  done
}

if [ "${1:-}" = "--self-test" ]; then
  tmp=$(mktemp)
  printf 'arn:aws:iam::987654321098:role/x\nexport AWS_PROFILE=gap-dev\nop://Private/x\n' > "$tmp"
  scan "$tmp" >/dev/null; n=$HITS; rm -f "$tmp"
  [ "$n" -ge 3 ] && { echo "self-test ok ($n planted hits found)"; exit 0; }
  echo "self-test FAILED: found $n of 3 planted identifiers"; exit 1
fi

FILES=()
while IFS= read -r f; do FILES+=("$f"); done < <(git ls-files | grep -v '^scripts/check-identifiers.sh$')
[ "${#FILES[@]}" -eq 0 ] && { echo "no tracked files"; exit 0; }
scan "${FILES[@]}"; n=$HITS
if [ "$n" -gt 0 ]; then
  echo "FAILED: $n identifier hit(s). Replace with a placeholder or remove."
  exit 1
fi
echo "ok: ${#FILES[@]} tracked files, 0 identifier hits"
