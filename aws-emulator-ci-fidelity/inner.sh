#!/bin/sh
# Inside unshare -rn: loopback only, so nothing can reach real AWS even by mistake.
set -eu
ip link set lo up
export HOME="$EMU_HOME"
"$EMU_BIN" --telemetry off --port 9297 > "$RAW/emulator.log" 2>&1 &
EPID=$!
i=0; until curl -sk https://127.0.0.1:9297/__admin/health >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 120 ] && { echo "emulator not healthy"; exit 1; }; sleep 0.5; done
export AWS_ENDPOINT_URL=https://127.0.0.1:9297 AWS_SHARED_CREDENTIALS_FILE=$HOME/.aws/emulator/9297/emulator_credentials \
  AWS_CONFIG_FILE=$HOME/.aws/emulator/9297/config AWS_CA_BUNDLE=$HOME/.aws/emulator/9297/ca.pem AWS_EC2_METADATA_DISABLED=true \
  AWS_DISABLE_HOST_PREFIX_INJECTION=true AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
"$PY" "$EXP/checks.py" "$RAW/checks.json" 2> "$RAW/checks.stderr"
"$PY" "$EXP/checks2.py" "$RAW/checks2.json" 2> "$RAW/checks2.stderr" || true
# Trap check: the same SDK call with AWS_ENDPOINT_URL missing. In a networked CI runner this would go to real AWS.
env -u AWS_ENDPOINT_URL "$PY" "$EXP/no_endpoint.py" > "$RAW/no-endpoint.txt" 2>&1 || true
env -u AWS_ENDPOINT_URL -u AWS_CONFIG_FILE "$PY" "$EXP/no_endpoint.py" > "$RAW/no-endpoint-no-config.txt" 2>&1 || true
kill $EPID
