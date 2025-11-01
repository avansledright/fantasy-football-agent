# IAM role for Lambda functions
resource "aws_iam_role" "web_lambda_role" {
  name = "fantasy-football-lambda-role"

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

# IAM policy for Lambda to access DynamoDB
resource "aws_iam_role_policy" "lambda_dynamodb_policy" {
  name = "fantasy-football-lambda-dynamodb-policy"
  role = aws_iam_role.web_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query"
        ]
        Resource = ["${aws_dynamodb_table.fantasy_football_team_roster.arn}", "${aws_dynamodb_table.fantasy_football_players.arn}"]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Archive the roster management Lambda function code
data "archive_file" "roster_management_zip" {
  type        = "zip"
  source_file = "${path.module}/web_lambda/lambda_function.py"
  output_path = "${path.module}/builds/web_lambda.zip"
}

# Lambda function for roster management
resource "aws_lambda_function" "roster_management" {
  filename      = data.archive_file.roster_management_zip.output_path
  function_name = "fantasy-football-roster-management"
  role          = aws_iam_role.web_lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 256  # Explicit allocation - prevents cold start issues with Python 3.12 + boto3

  source_code_hash = data.archive_file.roster_management_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.fantasy_football_team_roster.name
      PLAYERS_TABLE  = aws_dynamodb_table.fantasy_football_players.name
    }
  }
}
