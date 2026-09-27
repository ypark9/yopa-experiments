#!/usr/bin/env bash
# Fail a pipeline unless the rollout really finished with the intended number of tasks
# on the intended task definition. `aws ecs wait services-stable` alone is not enough:
# it succeeds when runningCount == desiredCount, including 0 == 0, and after a rollback.
#
# usage: check-rollout.sh <cluster> <service> <expected-task-def-arn> <expected-count>
set -euo pipefail
cluster=$1 service=$2 want_td=$3 want_n=$4
read -r state td running desired < <(aws ecs describe-services --cluster "$cluster" --services "$service" \
  --query 'services[0].deployments[?status==`PRIMARY`] | [0].[rolloutState, taskDefinition, runningCount, desiredCount]' \
  --output text)
echo "primary: rolloutState=$state running=$running desired=$desired taskDef=${td##*/}"
fail=0
[ "$state" = "COMPLETED" ] || { echo "FAIL: rolloutState is $state, not COMPLETED"; fail=1; }
[ "$td" = "$want_td" ] || { echo "FAIL: primary runs ${td##*/}, expected ${want_td##*/} (rolled back?)"; fail=1; }
[ "$desired" -ge "$want_n" ] || { echo "FAIL: desiredCount is $desired, expected at least $want_n (IaC reset it?)"; fail=1; }
[ "$running" -ge "$want_n" ] || { echo "FAIL: runningCount is $running, expected at least $want_n"; fail=1; }
[ "$fail" = 0 ] && echo "OK: rollout complete with $running task(s) on ${td##*/}"
exit "$fail"
