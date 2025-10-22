data "archive_file" "waiver_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/waiver-scraper/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

# IAM role for Lambda function
resource "aws_iam_role" "waiver_lambda_role" {
  name = "fantasy-football-waiver-lambda-role"

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
    Environment = var.environment
    Purpose     = "Fantasy Football Lambda Role"
  }
}

# IAM policy for Lambda basic execution
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.waiver_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# IAM policy for DynamoDB access
resource "aws_iam_role_policy" "waiver_lambda_dynamodb_policy" {
  name = "fantasy-football-lambda-dynamodb-policy"
  role = aws_iam_role.waiver_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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

# Lambda function
resource "aws_lambda_function" "waiver_wire_lambda" {
  filename         = data.archive_file.waiver_lambda_zip.output_path
  function_name    = "fantasy-football-waiver-wire"
  role             = aws_iam_role.waiver_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.waiver_lambda_zip.output_base64sha256
  runtime          = "python3.12"
  timeout          = 300 # 5 minutes
  memory_size      = 512
  layers           = [aws_lambda_layer_version.python_dependencies.arn]
  environment {
    variables = {
      LEAGUE_ID         = var.espn_league_id
      SEASON_ID         = "2025"
      PLAYER_TABLE_NAME = aws_dynamodb_table.fantasy_football_player_data.name
      ESPN_S2           = var.espn_s2_value
      SWID              = var.espn_swid
      ROSTER_TABLE_NAME = aws_dynamodb_table.fantasy_football_team_roster.name
      CURRENT_WEEK = "8"
      WEEKS_AHEAD = "11"

    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy.lambda_dynamodb_policy,
    aws_cloudwatch_log_group.lambda_logs
  ]

  tags = {
    Project     = "fantasy-football"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}

# EventBridge rule to trigger Lambda daily at noon CST
resource "aws_cloudwatch_event_rule" "daily_waiver_update" {
  name                = "fantasy-football-daily-waiver-update"
  description         = "Trigger waiver wire update daily at noon CST"
  schedule_expression = "cron(0 18 * * ? *)" # 18:00 UTC = 12:00 CST (accounting for CDT/CST)

  tags = {
    Environment = var.environment
    Purpose     = "Fantasy Football Daily Schedule"
  }
}

# EventBridge target to invoke Lambda
resource "aws_cloudwatch_event_target" "waiver_lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_waiver_update.name
  target_id = "fantasy-football-lambda-target"
  arn       = aws_lambda_function.waiver_wire_lambda.arn
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "waiver_allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.waiver_wire_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_waiver_update.arn
}