import * as cdk from "aws-cdk-lib";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as agentcore from "@aws-cdk/aws-bedrock-agentcore-alpha";
import * as bedrock from "@aws-cdk/aws-bedrock-alpha";
import * as path from "path";
import { Construct } from "constructs";

export class LineAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // --- DynamoDB Tables ---

    // Google OAuth2 トークン管理テーブル
    const tokenTable = new dynamodb.Table(this, "GoogleOAuthTokens", {
      tableName: "GoogleOAuthTokens",
      partitionKey: { name: "line_user_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
    });

    // ユーザーセッションステートテーブル (TTL 付き)
    const stateTable = new dynamodb.Table(this, "UserSessionState", {
      tableName: "UserSessionState",
      partitionKey: { name: "line_user_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: "ttl",
    });

    // --- AgentCore Runtime (既存: 汎用 Agent) ---
    const agentRuntimeArtifact = agentcore.AgentRuntimeArtifact.fromAsset(
      path.join(__dirname, "../../agent"),
    );

    const runtime = new agentcore.Runtime(this, "StrandsAgentRuntime", {
      runtimeName: "lineAssistantAgent",
      agentRuntimeArtifact,
      description: "LINE AI Assistant - Strands Agent with Claude Sonnet 4.5",
      environmentVariables: {
        LOG_LEVEL: "INFO",
        BEDROCK_MODEL_ID: "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        TAVILY_API_KEY: process.env.TAVILY_API_KEY ?? "",
        BEDROCK_MEMORY_ID: process.env.BEDROCK_MEMORY_ID ?? "",
      },
    });

    runtime.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: [
          `arn:aws:bedrock:*::foundation-model/anthropic.*`,
          `arn:aws:bedrock:*::foundation-model/us.anthropic.*`,
        ],
      }),
    );

    // Bedrock AgentCore Memory 操作権限
    runtime.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:GetMemory",
          "bedrock:CreateMemory",
          "bedrock:UpdateMemory",
          "bedrock:DeleteMemory",
          "bedrock:CreateSession",
          "bedrock:GetSession",
          "bedrock:UpdateSession",
          "bedrock:DeleteSession",
          "bedrock:ListSessions",
          "bedrock:PutSessionEvent",
        ],
        resources: ["*"],
      }),
    );

    // --- AgentCore Runtime (Calendar Agent) ---
    const calendarAgentArtifact = agentcore.AgentRuntimeArtifact.fromAsset(
      path.join(__dirname, "../../agent"),
      {
        file: "Dockerfile.calendar",
      },
    );

    const calendarRuntime = new agentcore.Runtime(this, "CalendarAgentRuntime", {
      runtimeName: "calendarAgent",
      agentRuntimeArtifact: calendarAgentArtifact,
      description: "Google Calendar Agent with Strands + Calendar API tools",
      environmentVariables: {
        LOG_LEVEL: "INFO",
        BEDROCK_MODEL_ID: "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
      },
    });

    calendarRuntime.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: [
          `arn:aws:bedrock:*::foundation-model/anthropic.*`,
          `arn:aws:bedrock:*::foundation-model/us.anthropic.*`,
        ],
      }),
    );

    // --- AgentCore Runtime (Gmail Agent) ---
    const gmailAgentArtifact = agentcore.AgentRuntimeArtifact.fromAsset(
      path.join(__dirname, "../../agent"),
      {
        file: "Dockerfile.gmail",
      },
    );

    const gmailRuntime = new agentcore.Runtime(this, "GmailAgentRuntime", {
      runtimeName: "gmailAgent",
      agentRuntimeArtifact: gmailAgentArtifact,
      description: "Google Gmail Agent with Strands + Gmail API tools",
      environmentVariables: {
        LOG_LEVEL: "INFO",
        BEDROCK_MODEL_ID: "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
      },
    });

    gmailRuntime.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: [
          `arn:aws:bedrock:*::foundation-model/anthropic.*`,
          `arn:aws:bedrock:*::foundation-model/us.anthropic.*`,
        ],
      }),
    );

    // --- Lambda Layer (dependencies) ---
    const depsLayer = new lambda.LayerVersion(this, "LambdaDepsLayer", {
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          platform: "linux/arm64",
          command: [
            "bash",
            "-c",
            [
              "pip install -r requirements.txt -t /asset-output/python",
              "--platform manylinux2014_aarch64",
              "--only-binary=:all:",
              "--python-version 3.13",
            ].join(" "),
          ],
        },
      }),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_13],
      compatibleArchitectures: [lambda.Architecture.ARM_64],
      description: "LINE Bot SDK, Google Auth, and dependencies",
    });

    // --- 共通環境変数 ---
    const commonEnv = {
      LINE_CHANNEL_SECRET: process.env.LINE_CHANNEL_SECRET ?? "",
      LINE_CHANNEL_ACCESS_TOKEN: process.env.LINE_CHANNEL_ACCESS_TOKEN ?? "",
      GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID ?? "",
      GOOGLE_CLIENT_SECRET: process.env.GOOGLE_CLIENT_SECRET ?? "",
      OAUTH_STATE_SECRET: process.env.OAUTH_STATE_SECRET ?? "",
      DYNAMODB_TOKEN_TABLE: tokenTable.tableName,
      USER_STATE_TABLE: stateTable.tableName,
      AWS_REGION_NAME: this.region,
      LOG_LEVEL: "INFO",
    };

    // --- Webhook Lambda Function ---
    const webhookFunction = new lambda.Function(this, "WebhookFunction", {
      runtime: lambda.Runtime.PYTHON_3_13,
      architecture: lambda.Architecture.ARM_64,
      handler: "index.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda"), {
        exclude: ["requirements.txt", "__pycache__", "*.pyc", "tests"],
      }),
      layers: [depsLayer],
      memorySize: 512,
      timeout: cdk.Duration.seconds(60),
      environment: {
        ...commonEnv,
        AGENT_RUNTIME_ARN: runtime.agentRuntimeArn,
        CALENDAR_AGENT_RUNTIME_ARN: calendarRuntime.agentRuntimeArn,
        GMAIL_AGENT_RUNTIME_ARN: gmailRuntime.agentRuntimeArn,
        DEV_WEBHOOK_URL: process.env.DEV_WEBHOOK_URL ?? "",
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant Lambda permissions
    runtime.grantInvokeRuntime(webhookFunction);
    calendarRuntime.grantInvokeRuntime(webhookFunction);
    gmailRuntime.grantInvokeRuntime(webhookFunction);
    tokenTable.grantReadWriteData(webhookFunction);
    stateTable.grantReadWriteData(webhookFunction);

    // --- OAuth Callback Lambda Function ---
    const oauthCallbackFunction = new lambda.Function(this, "OAuthCallbackFunction", {
      runtime: lambda.Runtime.PYTHON_3_13,
      architecture: lambda.Architecture.ARM_64,
      handler: "oauth_callback.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda"), {
        exclude: ["requirements.txt", "__pycache__", "*.pyc", "tests"],
      }),
      layers: [depsLayer],
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      environment: {
        ...commonEnv,
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant OAuth callback Lambda permissions
    tokenTable.grantReadWriteData(oauthCallbackFunction);

    // --- API Gateway ---
    const api = new apigateway.RestApi(this, "LineWebhookApi", {
      restApiName: "LINE Webhook API",
      description: "LINE AI Assistant Webhook endpoint",
      deployOptions: {
        stageName: "prod",
        throttlingRateLimit: 100,
        throttlingBurstLimit: 50,
      },
    });

    // POST /callback - LINE Webhook
    const callbackResource = api.root.addResource("callback");
    callbackResource.addMethod(
      "POST",
      new apigateway.LambdaIntegration(webhookFunction),
    );

    // GET /oauth/callback - Google OAuth2 Callback
    const oauthResource = api.root.addResource("oauth");
    const oauthCallbackResource = oauthResource.addResource("callback");
    oauthCallbackResource.addMethod(
      "GET",
      new apigateway.LambdaIntegration(oauthCallbackFunction),
    );

    // --- Outputs ---
    new cdk.CfnOutput(this, "WebhookUrl", {
      value: `${api.url}callback`,
      description: "LINE Webhook URL (set in LINE Developer Console)",
    });

    new cdk.CfnOutput(this, "OAuthCallbackUrl", {
      value: `${api.url}oauth/callback`,
      description: "Google OAuth2 Redirect URI (set in GCP Console)",
    });

    new cdk.CfnOutput(this, "RuntimeArn", {
      value: runtime.agentRuntimeArn,
      description: "AgentCore Runtime ARN (General Agent)",
    });

    new cdk.CfnOutput(this, "CalendarRuntimeArn", {
      value: calendarRuntime.agentRuntimeArn,
      description: "AgentCore Runtime ARN (Calendar Agent)",
    });

    new cdk.CfnOutput(this, "GmailRuntimeArn", {
      value: gmailRuntime.agentRuntimeArn,
      description: "AgentCore Runtime ARN (Gmail Agent)",
    });

    new cdk.CfnOutput(this, "RuntimeName", {
      value: runtime.agentRuntimeName,
      description: "AgentCore Runtime Name",
    });

    new cdk.CfnOutput(this, "TokenTableName", {
      value: tokenTable.tableName,
      description: "DynamoDB Token Table Name",
    });
  }
}
