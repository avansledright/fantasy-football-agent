resource "aws_cloudwatch_event_rule" "daily_roster_update" {
  name                = "${var.agent_name}-daily-roster-update"
  schedule_expression = "cron(0 8 * * ? *)" # 8 UTC = 3am ET
}

resource "aws_cloudwatch_event_target" "roster_lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_roster_update.name
  target_id = "RosterLambda"
  arn       = aws_lambda_function.roster_scraper.arn
}

resource "aws_lambda_permission" "allow_eventbridge_roster_scraper" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.roster_scraper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_roster_update.arn
}

data "archive_file" "roster_scraper_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/roster_scraper_lambda"
  output_path = "${path.module}/roster_scraper_lambda.zip"
}

resource "aws_iam_role" "roster_scraper_lambda" {
  name = "roster-scraper-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "roster_scraper_logs" {
  role       = aws_iam_role.roster_scraper_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "roster_scraper_dynamodb" {
  name        = "roster-scraper-dynamodb-policy"
  description = "Allow roster scraper Lambda to read/write to the fantasy_football_team_roster table"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:BatchGetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ],
        Resource = [
          "${aws_dynamodb_table.fantasy_football_team_roster.arn}",
          "${aws_dynamodb_table.fantasy_football_team_roster.arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "roster_scraper_dynamodb_attach" {
  role       = aws_iam_role.roster_scraper_lambda.name
  policy_arn = aws_iam_policy.roster_scraper_dynamodb.arn
}

resource "aws_lambda_function" "roster_scraper" {
  function_name    = "${var.agent_name}-roster-scraper"
  filename         = data.archive_file.roster_scraper_lambda_zip.output_path
  source_code_hash = data.archive_file.roster_scraper_lambda_zip.output_base64sha256

  handler     = "lambda_function.lambda_handler"
  runtime     = "python3.12"
  timeout     = 60
  memory_size = 256

  role   = aws_iam_role.roster_scraper_lambda.arn
  layers = [aws_lambda_layer_version.python_dependencies.arn]

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.fantasy_football_team_roster.name
      ESPN_LEAGUE_ID      = var.espn_league_id
      ESPN_SWID           = var.espn_swid
      ESPN_S2        = var.espn_s2_value
      SEASON_YEAR    = "2025"
    }
  }
  tags = {
    Project     = "fantasy-football"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}
