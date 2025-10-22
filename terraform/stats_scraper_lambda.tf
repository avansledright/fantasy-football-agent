# Create IAM role for Lambda function
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.lambda_function_name}-execution-role"

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
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}

# IAM policy for Lambda function
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.lambda_function_name}-policy"
  role = aws_iam_role.lambda_execution_role.id

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
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.lambda_function_name}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          "${aws_dynamodb_table.waiver_table.arn}",
          "${aws_dynamodb_table.waiver_table.arn}/index/*",
          "${aws_dynamodb_table.fantasy_football_team_roster.arn}",
          "${aws_dynamodb_table.fantasy_football_player_data.arn}",
          "${aws_dynamodb_table.fantasy_football_player_data.arn}/index/*"
        ]
      }
    ]
  })
}

# Create Lambda deployment package
data "archive_file" "stats_scarpe_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/stat_scraper_lambda"
  output_path = "fantasy_stats_scraper.zip"
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "stats_scarper_lambda_zip" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14

  tags = {
    Project     = "fantasy-football"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}

# EventBridge (CloudWatch Events) rule to trigger Lambda on Tuesdays at noon
resource "aws_cloudwatch_event_rule" "tuesday_noon_trigger" {
  name                = "${var.lambda_function_name}-tuesday-trigger"
  description         = "Trigger fantasy stats collection every Tuesday at noon ET"
  schedule_expression = "cron(0 15 ? * TUE *)" # 17:00 UTC = 12:00 PM ET (accounting for EST/EDT)

  tags = {
    Project     = "fantasy-football"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}

# EventBridge target
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.tuesday_noon_trigger.name
  target_id = "fantasy-stats-lambda-target"
  arn       = aws_lambda_function.fantasy_stats_scraper_with_layer.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fantasy_stats_scraper_with_layer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.tuesday_noon_trigger.arn
}

# Attach the layer to the Lambda function
resource "aws_lambda_function" "fantasy_stats_scraper_with_layer" {
  filename      = data.archive_file.stats_scarpe_lambda_zip.output_path
  function_name = var.lambda_function_name
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = 900
  memory_size   = 1024
  layers        = [aws_lambda_layer_version.python_dependencies.arn]

  source_code_hash = data.archive_file.stats_scarpe_lambda_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.fantasy_football_player_data.name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = {
    Project     = "fantasy-football"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}