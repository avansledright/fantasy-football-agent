data "archive_file" "depth_chart_api_zip" {
  type        = "zip"
  source_dir  = "${path.module}/depth_chart_api_lambda"
  output_path = "${path.module}/builds/depth_chart_api.zip"
}

resource "aws_iam_role" "depth_chart_api_lambda_role" {
  name = "${var.agent_name}-depth-chart-api-role"

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

resource "aws_iam_role_policy_attachment" "depth_chart_api_lambda_basic" {
  role       = aws_iam_role.depth_chart_api_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "depth_chart_api" {
  filename         = data.archive_file.depth_chart_api_zip.output_path
  function_name    = "${var.agent_name}-depth-chart-api"
  role            = aws_iam_role.depth_chart_api_lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.12"
  timeout         = 30
  memory_size     = 512
  architectures   = ["arm64"]
  source_code_hash = data.archive_file.depth_chart_api_zip.output_base64sha256

  layers = [aws_lambda_layer_version.python_dependencies.arn]

  environment {
    variables = {
      LOG_LEVEL = var.lambda_log_level
    }
  }

  tags = {
    Project     = "fantasy-football"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_cloudwatch_log_group" "depth_chart_api_logs" {
  name              = "/aws/lambda/${aws_lambda_function.depth_chart_api.function_name}"
  retention_in_days = 3

  tags = {
    Project     = "fantasy-football"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_api_gateway_resource" "depth_chart" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "depth-chart"
}

resource "aws_api_gateway_method" "depth_chart_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.depth_chart.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "depth_chart_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.depth_chart.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "depth_chart_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.depth_chart.id
  http_method             = aws_api_gateway_method.depth_chart_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.depth_chart_api.invoke_arn
}

resource "aws_api_gateway_integration" "depth_chart_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.depth_chart.id
  http_method = aws_api_gateway_method.depth_chart_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "depth_chart_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.depth_chart.id
  http_method = aws_api_gateway_method.depth_chart_options.http_method
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

resource "aws_api_gateway_integration_response" "depth_chart_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.depth_chart.id
  http_method = aws_api_gateway_method.depth_chart_options.http_method
  status_code = aws_api_gateway_method_response.depth_chart_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.depth_chart_options]
}

resource "aws_lambda_permission" "apigw_depth_chart" {
  statement_id  = "AllowAPIGatewayInvokeDepthChart"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.depth_chart_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}
