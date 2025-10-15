# ===============================================
# Chat Manager Lambda Function Infrastructure
# ===============================================

# Lambda function for chat functionality
resource "aws_lambda_function" "chat_manager" {
  filename         = data.archive_file.chat_manager_zip.output_path
  function_name    = "${var.agent_name}-chat-manager"
  role            = aws_iam_role.lambda_role_chat.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.12"
  source_code_hash = data.archive_file.chat_manager_zip.output_base64sha256
  timeout         = 60
  memory_size     = 512
  architectures = ["arm64"]

  layers = [
    aws_lambda_layer_version.python_dependencies.arn
  ]

  environment {
  variables = {
    AGENT_NAME = var.agent_name
    CHAT_HISTORY_TABLE = aws_dynamodb_table.chat_history.name
    FANTASY_PLAYERS_TABLE=aws_dynamodb_table.fantasy_football_players.name
    FANTASY_ROSTER_TABLE=aws_dynamodb_table.fantasy_football_team_roster.name
    FANTASY_WAIVER_TABLE=aws_dynamodb_table.waiver_table.name
    BEDROCK_MODEL_ID="us.anthropic.claude-sonnet-4-20250514-v1:0"
  }
}

  tags = {
    Name        = "${var.agent_name}-chat-manager"
    Environment = var.environment
    Service     = "chat"
  }
}

# Create the Lambda deployment package
data "archive_file" "chat_manager_zip" {
  type        = "zip"
  source_dir  = "${path.module}/chat-lambda"
  output_path = "${path.module}/chat-lambda.zip"
}

# IAM role for the chat Lambda function
resource "aws_iam_role" "lambda_role_chat" {
  name = "${var.agent_name}-lambda-chat-role"

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
    Name        = "${var.agent_name}-lambda-chat-role"
    Environment = var.environment
    Service     = "chat"
  }
}

# IAM policy for the chat Lambda function
resource "aws_iam_role_policy" "lambda_policy_chat" {
  name = "${var.agent_name}-lambda-chat-policy"
  role = aws_iam_role.lambda_role_chat.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          "${aws_dynamodb_table.chat_history.arn}",
          "${aws_dynamodb_table.chat_history.arn}/*",
          "${aws_dynamodb_table.fantasy_football_team_roster.arn}",
          "${aws_dynamodb_table.fantasy_football_team_roster.arn}/*",
          "${aws_dynamodb_table.waiver_table.arn}",
          "${aws_dynamodb_table.waiver_table.arn}/*",
          "${aws_dynamodb_table.fantasy_football_players.arn}",
          "${aws_dynamodb_table.fantasy_football_players.arn}/*",
        ]
      }
    ]
  })
}

# Attach the AWS Lambda basic execution role policy
resource "aws_iam_role_policy_attachment" "lambda_basic_execution_chat" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role_chat.name
}

# CloudWatch Log Group for Chat Lambda
resource "aws_cloudwatch_log_group" "chat_manager_logs" {
  name              = "/aws/lambda/${aws_lambda_function.chat_manager.function_name}"
  retention_in_days = 3

  tags = {
    Name        = "${var.agent_name}-chat-manager-logs"
    Environment = var.environment
    Service     = "chat"
  }
}

# DynamoDB table for storing chat history (optional)
resource "aws_dynamodb_table" "chat_history" {
  name           = "${var.agent_name}-chat-history"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "session_id"
  range_key      = "timestamp"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "team_id"
    type = "S"
  }

  global_secondary_index {
    name     = "team-id-index"
    hash_key = "team_id"
    range_key = "timestamp"
    projection_type    = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name        = "${var.agent_name}-chat-history"
    Environment = var.environment
    Service     = "chat"
  }
}