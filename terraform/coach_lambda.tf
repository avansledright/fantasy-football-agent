resource "aws_iam_role" "coach_lambda_role" {
  name = "coach-lambda-role"

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
}

resource "aws_iam_policy" "coach_lambda_extra_policy" {
  name        = "coach-lambda-extra-policy"
  description = "Allow coach Lambda to read DynamoDB and invoke Bedrock models"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/fantasy-football-*"
        ]
      },
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

resource "aws_iam_role_policy_attachment" "coach_lambda_extra_attach" {
  role       = aws_iam_role.coach_lambda_role.name
  policy_arn = aws_iam_policy.coach_lambda_extra_policy.arn
}

resource "aws_iam_role_policy_attachment" "coach_lambda_policy" {
  role       = aws_iam_role.coach_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "coach" {
  function_name    = var.coach_function_name
  role             = aws_iam_role.coach_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 512
  architectures    = ["arm64"]
  filename         = data.archive_file.coach_lambda_zip.output_path
  source_code_hash = data.archive_file.coach_lambda_zip.output_base64sha256
  layers = [
    aws_lambda_layer_version.python_dependencies.arn
  ]
  environment {
    variables = {
      BEDROCK_MODEL_ID     = "us.anthropic.claude-sonnet-4-20250514-v1:0"
      PLAYERS_TABLE      = aws_dynamodb_table.fantasy_football_players.name
      DDB_TABLE_ROSTER     = aws_dynamodb_table.fantasy_football_team_roster.name
      DEFAULT_TEAM_ID      = "7"
      SCORING              = "PPR"
      LINEUP_SLOTS         = "QB,RB,RB,WR,WR,TE,FLEX,OP,K,DST"
    }
  }

  depends_on = [aws_iam_role_policy_attachment.coach_lambda_extra_attach, data.archive_file.coach_lambda_zip]
}

resource "aws_lambda_permission" "apigw_coach" {
  statement_id  = "AllowAPIGatewayInvokeCoach"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.coach.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}