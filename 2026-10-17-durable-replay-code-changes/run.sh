#!/bin/sh
# Runs the whole experiment locally. No AWS account, credentials or network:
# the harness runs with an empty environment, AWS config pointed at /dev/null,
# and (when unshare is available) inside a network namespace with no
# interfaces, so any AWS API call would fail instead of reaching AWS.
set -eu
cd "$(dirname "$0")"
mkdir -p results

# 1. Refuse to run if AWS credentials are visible.
if env | grep -q '^AWS_\(ACCESS_KEY_ID\|SECRET_ACCESS_KEY\|SESSION_TOKEN\|PROFILE\)='; then
  echo "AWS credentials in the environment; refusing to run" >&2; exit 1
fi
for f in "$HOME/.aws/credentials" "$HOME/.aws/config"; do
  if [ -e "$f" ]; then echo "found $f; refusing to run" >&2; exit 1; fi
done

# 2. Versions.
{
  go version
  go list -m github.com/aws/aws-durable-execution-sdk-go
  go version -m "$(command -v durablelint)" | grep -E 'mod|go1' | sed 's#^.*/durablelint:#durablelint:#'
} > results/versions.txt

# 3. Static check.
# durablelint exits non-zero when it reports findings; that is expected here.
# Absolute paths are cut so the output does not depend on the checkout path.
durablelint ./cases/... 2>&1 | sed "s#$PWD/##g" > results/durablelint.txt || true
durablelint -json ./cases/... 2>&1 | sed "s#$PWD/##g" > results/durablelint.json || true

# 4. Trials.
go build -o ./replaylab.bin .
NONET=""
if unshare -rn true 2>/dev/null; then NONET="unshare -rn"; fi
echo "network isolation: ${NONET:-none}" >> results/versions.txt
for run in 1 2 3; do
  env -i PATH=/usr/bin:/bin HOME=/nonexistent \
    AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true \
    $NONET ./replaylab.bin -trials 20 -run "$run" \
    > "results/run-$run.jsonl" 2> "results/run-$run.tally.txt"
done
rm -f ./replaylab.bin

# 5. Supplementary probes (invocation counts, wait duration, RequestID, timing).
GOC="$(go env GOCACHE)"; GOM="$(go env GOMODCACHE)"; GOBIN_DIR="$(dirname "$(command -v go)")"
env -i PATH="$GOBIN_DIR:/usr/bin:/bin" HOME=/nonexistent GOCACHE="$GOC" GOMODCACHE="$GOM" \
  GOFLAGS=-mod=mod GOTOOLCHAIN=local GOPROXY=off \
  AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true \
  $NONET go test ./probes -v -count=1 > results/probes.txt 2>&1
python3 summarize.py > results/matrix.md
cat results/matrix.md
