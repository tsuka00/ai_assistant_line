import * as cdk from "aws-cdk-lib";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
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

    // --- AgentCore Runtime ---
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
      },
    });

    // Grant Bedrock model invocation to the runtime
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

    // --- Lambda Layer (line-bot-sdk) ---
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
      description: "LINE Bot SDK and dependencies",
    });

    // --- Lambda Function ---
    const webhookFunction = new lambda.Function(this, "WebhookFunction", {
      runtime: lambda.Runtime.PYTHON_3_13,
      architecture: lambda.Architecture.ARM_64,
      handler: "index.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda"), {
        exclude: ["requirements.txt", "__pycache__", "*.pyc"],
      }),
      layers: [depsLayer],
      memorySize: 512,
      timeout: cdk.Duration.seconds(60),
      environment: {
        LINE_CHANNEL_SECRET: process.env.LINE_CHANNEL_SECRET ?? "",
        LINE_CHANNEL_ACCESS_TOKEN: process.env.LINE_CHANNEL_ACCESS_TOKEN ?? "",
        AGENT_RUNTIME_ARN: runtime.agentRuntimeArn,
        AWS_REGION_NAME: this.region,
        LOG_LEVEL: "INFO",
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant Lambda permission to invoke AgentCore Runtime
    runtime.grantInvokeRuntime(webhookFunction);

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

    const callbackResource = api.root.addResource("callback");
    callbackResource.addMethod(
      "POST",
      new apigateway.LambdaIntegration(webhookFunction),
    );

    // --- Outputs ---
    new cdk.CfnOutput(this, "WebhookUrl", {
      value: `${api.url}callback`,
      description: "LINE Webhook URL (set in LINE Developer Console)",
    });

    new cdk.CfnOutput(this, "RuntimeArn", {
      value: runtime.agentRuntimeArn,
      description: "AgentCore Runtime ARN",
    });

    new cdk.CfnOutput(this, "RuntimeName", {
      value: runtime.agentRuntimeName,
      description: "AgentCore Runtime Name",
    });
  }
}
