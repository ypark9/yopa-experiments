// yopa.page PR #104 PoC: does `aws ecs wait services-stable` succeed on a service with 0 tasks?
// L1 constructs only, so there is no VPC lookup and no IAM role. No task ever runs.
const cdk = require("aws-cdk-lib");
const ecs = require("aws-cdk-lib/aws-ecs");

const app = new cdk.App();
const subnets = (app.node.tryGetContext("subnets") || "").split(",").filter(Boolean);
if (subnets.length === 0) throw new Error("pass -c subnets=subnet-a,subnet-b");

const stack = new cdk.Stack(app, "ecs-stable-demo", {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: "us-east-1" },
  description: "yopa.page PR #104 PoC: services-stable on a 0-task service. No tasks run.",
});
cdk.Tags.of(stack).add("Lifecycle", "disposable");
cdk.Tags.of(stack).add("Purpose", "yopa-blog-pr104");

const cluster = new ecs.CfnCluster(stack, "Cluster", { clusterName: "ecs-stable-demo" });
const td = new ecs.CfnTaskDefinition(stack, "TaskDef", {
  family: "ecs-stable-demo",
  requiresCompatibilities: ["FARGATE"],
  networkMode: "awsvpc",
  cpu: "256",
  memory: "512",
  containerDefinitions: [
    { name: "probe", image: "public.ecr.aws/docker/library/busybox:latest", command: ["sleep", "3600"], essential: true },
  ],
});
new ecs.CfnService(stack, "Service", {
  serviceName: "ecs-stable-demo",
  cluster: cluster.ref,
  taskDefinition: td.ref,
  launchType: "FARGATE",
  desiredCount: 0,
  deploymentConfiguration: {
    minimumHealthyPercent: 0,
    maximumPercent: 100,
    deploymentCircuitBreaker: { enable: true, rollback: true },
  },
  networkConfiguration: { awsvpcConfiguration: { assignPublicIp: "DISABLED", subnets } },
});
