# Does `aws ecs wait services-stable` pass on a service with zero tasks?

Code and output for [ECS Deployments Can Say 'Completed' With Nothing Running](https://www.yopa.page/blog/2026-09-27-ecs-deployment-observability.html).

## What it does

- Deploys **one CDK stack**: an ECS cluster, a Fargate task definition (busybox, no IAM role), and one
  service with `desiredCount: 0` and the circuit breaker on. L1 constructs only, so no VPC lookup and no IAM.
- Forces a new deployment, times `aws ecs wait services-stable`, then runs `check-rollout.sh` expecting 1 task.
- **No task ever runs**, so it costs nothing. You pass two existing private subnet IDs; nothing else in your
  account is read or changed.
- Delete afterwards with `cd cdk && npx cdk destroy`.

## Result (2026-09-27)

```
10:37:31.9  force-new-deployment   PRIMARY IN_PROGRESS, desired 0, running 0
10:38:34    services-stable        exit 0 after 63 s   (desired 0, running 0, PRIMARY still IN_PROGRESS)
10:38:59    ECS event              deployment completed, steady state
check-rollout.sh                   exit 1: rolloutState IN_PROGRESS, desiredCount 0, runningCount 0
```

The waiter's success condition in botocore (`botocore/data/ecs/2014-11-13/waiters-2.json`):

```
length(services[?!(length(deployments) == `1` && runningCount == desiredCount)]) == `0`
```

## What this does not prove

- The rollback case (a circuit breaker rollback also leaves one deployment with matching counts) is
  read from the waiter definition, not triggered here.
- One run, one Region.

## Files

| File | |
| --- | --- |
| `cdk/app.js` | the stack |
| `run.sh` | deploy, force a deployment, time the waiter, run the check |
| `check-rollout.sh` | the check that fails unless the new revision runs the intended count |
| `output-2026-09-27.txt` | raw output of the run, identifiers redacted |
