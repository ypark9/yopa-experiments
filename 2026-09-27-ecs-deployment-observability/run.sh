#!/bin/bash
# Deploys ONE stack (ECS cluster + Fargate task definition + service with desiredCount 0),
# forces a new deployment, times `aws ecs wait services-stable`, then runs check-rollout.sh.
# No task ever runs, so it costs nothing. Delete afterwards with: (cd cdk && npx cdk destroy)
#
# usage: AWS_PROFILE=<your-profile> SUBNETS=subnet-aaa,subnet-bbb ./run.sh
set -u
: "${AWS_PROFILE:?set AWS_PROFILE to a test account profile}"
: "${SUBNETS:?set SUBNETS to two private subnet IDs}"
export AWS_REGION=${AWS_REGION:-us-east-1}
S=ecs-stable-demo
cd "$(dirname "$0")"
( cd cdk && npm install --silent && npx cdk deploy -c subnets="$SUBNETS" --require-approval never ) || { echo "deploy failed, stop"; exit 1; }
TD=$(aws ecs describe-services --cluster $S --services $S --query 'services[0].taskDefinition' --output text)
aws ecs update-service --cluster $S --service $S --force-new-deployment \
  --query 'service.deployments[].[status,rolloutState,desiredCount,runningCount]' --output text
T0=$(date +%s); aws ecs wait services-stable --cluster $S --services $S; RC=$?; T1=$(date +%s)
echo "services-stable exit=$RC after $((T1-T0))s"
aws ecs describe-services --cluster $S --services $S \
  --query 'services[0].[desiredCount,runningCount,deployments[0].rolloutState]' --output text
bash check-rollout.sh $S $S "$TD" 1; echo "check-rollout exit=$?"
