# Unified Coach Lambda - combines lineup optimization + conversational analysis
# This is a NEW parallel system alongside existing coach and chat lambdas

# ===== NEW DynamoDB Table for Unified Coach Chat History =====
resource "aws_dynamodb_table" "unified_chat_history" {
  name         = "fantasy-football-unified-chat-history"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "session_id"
  range_key = "timestamp"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name        = "fantasy-football-unified-chat-history"
    Project     = "fantasy-football"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ===== Lambda Package =====
data "archive_file" "unified_coach_zip" {
  type        = "zip"
  source_dir  = "${path.module}/unified-coach-lambda"
  output_path = "${path.module}/builds/unified_coach.zip"
}

# ===== IAM Role for Unified Coach Lambda =====
resource "aws_iam_role" "unified_coach_lambda_role" {
  name = "${var.agent_name}-unified-coach-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project     = "fantasy-football"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Basic execution role
resource "aws_iam_role_policy_attachment" "unified_coach_lambda_basic" {
  role       = aws_iam_role.unified_coach_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access policy
resource "aws_iam_role_policy" "unified_coach_dynamodb" {
  name = "${var.agent_name}-unified-coach-dynamodb"
  role = aws_iam_role.unified_coach_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem"
        ]
        Resource = [
          aws_dynamodb_table.fantasy_football_team_roster.arn,
          aws_dynamodb_table.fantasy_football_player_data.arn,
          aws_dynamodb_table.unified_chat_history.arn,
          "${aws_dynamodb_table.unified_chat_history.arn}/*"
        ]
      }
    ]
  })
}

# Bedrock access policy
resource "aws_iam_role_policy" "unified_coach_bedrock" {
  name = "${var.agent_name}-unified-coach-bedrock"
  role = aws_iam_role.unified_coach_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      }
    ]
  })
}

# ===== Lambda Function =====
resource "aws_lambda_function" "unified_coach" {
  filename         = data.archive_file.unified_coach_zip.output_path
  function_name    = "${var.agent_name}-unified-coach"
  role            = aws_iam_role.unified_coach_lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.12"
  timeout         = 300
  memory_size     = 1024
  architectures   = ["arm64"]
  source_code_hash = data.archive_file.unified_coach_zip.output_base64sha256

  layers = [aws_lambda_layer_version.python_dependencies.arn]

  environment {
    variables = {
      BEDROCK_MODEL_ID              = "us.anthropic.claude-sonnet-4-20250514-v1:0"
      FANTASY_PLAYERS_TABLE         = aws_dynamodb_table.fantasy_football_player_data.name
      FANTASY_ROSTER_TABLE          = aws_dynamodb_table.fantasy_football_team_roster.name
      UNIFIED_CHAT_HISTORY_TABLE    = aws_dynamodb_table.unified_chat_history.name
      LOG_LEVEL                     = var.lambda_log_level
      API_GATEWAY_ID                = aws_api_gateway_rest_api.main.id
      API_GATEWAY_REGION            = var.aws_region
      API_GATEWAY_STAGE             = aws_api_gateway_stage.demo.stage_name
    }
  }

  tags = {
    Name        = "fantasy-football-unified-coach"
    Project     = "fantasy-football"
    Environment = var.environment
    Service     = "unified-coach"
    ManagedBy   = "terraform"
  }
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "unified_coach_logs" {
  name              = "/aws/lambda/${aws_lambda_function.unified_coach.function_name}"
  retention_in_days = 14

  tags = {
    Project     = "fantasy-football"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ===== API Gateway Integration =====

# /unified-coach resource
resource "aws_api_gateway_resource" "unified_coach" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "unified-coach"
}

# POST method
resource "aws_api_gateway_method" "unified_coach_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.unified_coach.id
  http_method   = "POST"
  authorization = "NONE"
}

# OPTIONS method for CORS
resource "aws_api_gateway_method" "unified_coach_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.unified_coach.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# Lambda integration
resource "aws_api_gateway_integration" "unified_coach_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.unified_coach.id
  http_method             = aws_api_gateway_method.unified_coach_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.unified_coach.invoke_arn
  timeout_milliseconds    = 70000
}

# OPTIONS integration (CORS)
resource "aws_api_gateway_integration" "unified_coach_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.unified_coach.id
  http_method = aws_api_gateway_method.unified_coach_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

# OPTIONS method response
resource "aws_api_gateway_method_response" "unified_coach_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.unified_coach.id
  http_method = aws_api_gateway_method.unified_coach_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

# OPTIONS integration response
resource "aws_api_gateway_integration_response" "unified_coach_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.unified_coach.id
  http_method = aws_api_gateway_method.unified_coach_options.http_method
  status_code = aws_api_gateway_method_response.unified_coach_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.unified_coach_options]
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "apigw_unified_coach" {
  statement_id  = "AllowAPIGatewayInvokeUnifiedCoach"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.unified_coach.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# ===== Outputs =====
output "unified_coach_api_url" {
  description = "Unified Coach API endpoint URL"
  value       = "${aws_api_gateway_stage.demo.invoke_url}/unified-coach"
}

output "unified_coach_lambda_name" {
  description = "Unified Coach Lambda function name"
  value       = aws_lambda_function.unified_coach.function_name
}
