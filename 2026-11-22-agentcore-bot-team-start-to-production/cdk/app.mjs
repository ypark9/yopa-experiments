// The minimal bot-team stack: one table, one memory, one runtime, one API.
// Synthesized locally to check it builds and to count resources. Not deployed.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { App, Stack, Duration } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import {
  AgentCoreRuntime,
  AgentRuntimeArtifact,
  Memory,
  Runtime,
  RuntimeNetworkConfiguration
} from 'aws-cdk-lib/aws-bedrockagentcore';

const here = path.dirname(fileURLToPath(import.meta.url));
const app = new App({ outdir: path.join(here, 'cdk.out') });
const stack = new Stack(app, 'BotTeamMinimal');

// 1. Bots and tools are rows: PK/SK plus one index to list them.
const table = new dynamodb.Table(stack, 'Bots', {
  partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST
});
table.addGlobalSecondaryIndex({
  indexName: 'GSI1',
  partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'GSI1SK', type: dynamodb.AttributeType.STRING }
});

// 2. Short-term memory only: the conversation the model reads next turn.
const memory = new Memory(stack, 'History', { memoryName: 'bot_team_history' });

// 3. One execution role for everything the agent code calls.
const role = new iam.Role(stack, 'RuntimeRole', {
  assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com')
});
role.addToPolicy(new iam.PolicyStatement({
  actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
  resources: ['arn:aws:bedrock:*::foundation-model/*', `arn:aws:bedrock:${stack.region}:${stack.account}:*`]
}));
role.addToPolicy(new iam.PolicyStatement({
  actions: ['bedrock-agentcore:CreateEvent', 'bedrock-agentcore:ListEvents', 'bedrock-agentcore:GetEvent'],
  resources: [memory.memoryArn]
}));
role.addToPolicy(new iam.PolicyStatement({
  // PutItem only because a lead bot can create bots.
  actions: ['dynamodb:GetItem', 'dynamodb:BatchGetItem', 'dynamodb:Query', 'dynamodb:PutItem'],
  resources: [table.tableArn, `${table.tableArn}/index/GSI1`]
}));
role.addToPolicy(new iam.PolicyStatement({
  actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
  resources: [`arn:aws:logs:${stack.region}:${stack.account}:log-group:/aws/bedrock-agentcore/runtimes/*`]
}));

// 4. One runtime runs every bot. Public network, 15-minute idle timeout,
//    and the custom header the API uses to pass the user through.
const runtime = new Runtime(stack, 'BotRuntime', {
  runtimeName: 'bot_team_runtime',
  agentRuntimeArtifact: AgentRuntimeArtifact.fromCodeAsset({
    path: path.join(here, '..', 'runtime'),
    runtime: AgentCoreRuntime.NODE_22,
    entrypoint: ['index.js']
  }),
  executionRole: role,
  networkConfiguration: RuntimeNetworkConfiguration.usingPublicNetwork(),
  lifecycleConfiguration: { idleRuntimeSessionTimeout: Duration.minutes(15) },
  requestHeaderConfiguration: { allowlistedHeaders: ['X-Amzn-Bedrock-AgentCore-Runtime-Custom-user'] },
  environmentVariables: { TABLE_NAME: table.tableName, MEMORY_ID: memory.memoryId }
});

// 5. The front door: a Lambda that calls InvokeAgentRuntime and passes the stream on.
//    The handler body is yours; this placeholder only lets the stack synthesize.
const api = new lambda.Function(stack, 'ApiFunction', {
  runtime: lambda.Runtime.NODEJS_22_X,
  handler: 'index.handler',
  code: lambda.Code.fromInline('exports.handler = async () => ({ statusCode: 501 });'),
  timeout: Duration.minutes(15),
  environment: { RUNTIME_ARN: runtime.agentRuntimeArn, TABLE_NAME: table.tableName }
});
runtime.grantInvokeRuntime(api);
table.grantReadWriteData(api);

// 6. Sign-in and HTTPS: Cognito users, a REST API that streams for up to 15 minutes.
const users = new cognito.UserPool(stack, 'Users');
users.addClient('WebClient');
// cloudWatchRole: false skips an account-wide logging role that has nothing to do with this app.
const rest = new apigw.RestApi(stack, 'BotApi', { cloudWatchRole: false });
const authorizer = new apigw.CognitoUserPoolsAuthorizer(stack, 'SignedIn', { cognitoUserPools: [users] });
rest.root.addResource('v1').addProxy({
  anyMethod: true,
  defaultIntegration: new apigw.LambdaIntegration(api, {
    responseTransferMode: apigw.ResponseTransferMode.STREAM,
    timeout: Duration.minutes(15)
  }),
  defaultMethodOptions: { authorizer, authorizationType: apigw.AuthorizationType.COGNITO }
});

app.synth();
