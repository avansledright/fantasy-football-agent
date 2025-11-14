# API Gateway account settings for CloudWatch logging
resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

# API Gateway REST API
resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.agent_name}-api"
  description = "API for Strands Agent Demo"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# Existing API Gateway Resource for Agent
resource "aws_api_gateway_resource" "agent" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "agent"
}

# Existing API Gateway Method for Agent
resource "aws_api_gateway_method" "agent_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.agent.id
  http_method   = "POST"
  authorization = "NONE"
}

# Existing API Gateway Integration for Agent
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.agent.id
  http_method             = aws_api_gateway_method.agent_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.draft_agent.invoke_arn
  timeout_milliseconds    = 70000
}

# Lambda permission for API Gateway (Agent)
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.draft_agent.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# CORS for Agent endpoint
resource "aws_api_gateway_method" "agent_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.agent.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "agent_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.agent.id
  http_method = aws_api_gateway_method.agent_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "agent_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.agent.id
  http_method = aws_api_gateway_method.agent_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "agent_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.agent.id
  http_method = aws_api_gateway_method.agent_options.http_method
  status_code = aws_api_gateway_method_response.agent_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# Existing Coach Resource
resource "aws_api_gateway_resource" "coach" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "coach"
}

# Existing Coach GET method
resource "aws_api_gateway_method" "coach_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.coach.id
  http_method   = "GET"
  authorization = "NONE"
}

# Existing Coach Integration
resource "aws_api_gateway_integration" "coach_get" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.coach.id
  http_method             = aws_api_gateway_method.coach_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.coach.invoke_arn
  timeout_milliseconds    = 70000
}

# Add CORS headers to existing Coach GET method
resource "aws_api_gateway_method_response" "coach_get_cors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.coach.id
  http_method = aws_api_gateway_method.coach_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

resource "aws_api_gateway_integration_response" "coach_get_cors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.coach.id
  http_method = aws_api_gateway_method.coach_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'*'"
  }
}

# CORS for Coach endpoint
resource "aws_api_gateway_method" "coach_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.coach.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "coach_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.coach.id
  http_method = aws_api_gateway_method.coach_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "coach_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.coach.id
  http_method = aws_api_gateway_method.coach_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "coach_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.coach.id
  http_method = aws_api_gateway_method.coach_options.http_method
  status_code = aws_api_gateway_method_response.coach_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# NEW: Teams Resource for roster management
resource "aws_api_gateway_resource" "teams" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "teams"
}

# NEW: GET method for retrieving team roster
resource "aws_api_gateway_method" "teams_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.teams.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.querystring.team_id" = true
  }
}

resource "aws_api_gateway_integration" "teams_get" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.teams.id
  http_method             = aws_api_gateway_method.teams_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.roster_management.invoke_arn
  timeout_milliseconds    = 70000
}

# NEW: PUT method for updating team roster
resource "aws_api_gateway_method" "teams_put" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.teams.id
  http_method   = "PUT"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "teams_put_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_put.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

resource "aws_api_gateway_integration" "teams_put" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.teams.id
  http_method             = aws_api_gateway_method.teams_put.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.roster_management.invoke_arn
  timeout_milliseconds    = 70000
}

resource "aws_api_gateway_integration_response" "teams_put_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_put.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'*'"
  }

  depends_on = [
    aws_api_gateway_method_response.teams_put_200,
    aws_api_gateway_integration.teams_put
  ]
}

# NEW: CORS for teams resource
resource "aws_api_gateway_method" "teams_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.teams.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "teams_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration" "teams_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "teams_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_options.http_method
  status_code = aws_api_gateway_method_response.teams_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,PUT,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# NEW: Chat Resource for AI chat functionality
resource "aws_api_gateway_resource" "chat" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "chat"
}

# NEW: POST method for chat messages
resource "aws_api_gateway_method" "chat_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.chat.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "chat_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.chat_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

resource "aws_api_gateway_integration" "chat_post" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.chat.id
  http_method             = aws_api_gateway_method.chat_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.chat_manager.invoke_arn
  timeout_milliseconds    = 70000
}

resource "aws_api_gateway_integration_response" "chat_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.chat_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'*'"
  }

  depends_on = [
    aws_api_gateway_method_response.chat_post_200,
    aws_api_gateway_integration.chat_post
  ]
}

# NEW: CORS for chat resource
resource "aws_api_gateway_method" "chat_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.chat.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "chat_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.chat_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration" "chat_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.chat_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "chat_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.chat_options.http_method
  status_code = aws_api_gateway_method_response.chat_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# NEW: Lambda permission for teams endpoint
resource "aws_lambda_permission" "api_gateway_invoke_roster" {
  statement_id  = "AllowExecutionFromAPIGatewayRoster"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.roster_management.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# NEW: Lambda permission for coach endpoint (if not already exists)
resource "aws_lambda_permission" "api_gateway_invoke_coach" {
  statement_id  = "AllowExecutionFromAPIGatewayCoach"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.coach.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# NEW: Lambda permission for chat endpoint
resource "aws_lambda_permission" "api_gateway_invoke_chat" {
  statement_id  = "AllowExecutionFromAPIGatewayChat"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chat_manager.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# Updated API Gateway Deployment with new resources
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  # Deployment triggers - includes API config AND Lambda code hashes
  # This ensures redeployment when either API structure or Lambda code changes
  triggers = {
    redeployment = sha1(jsonencode([
      # API Gateway resources
      aws_api_gateway_resource.agent.id,
      aws_api_gateway_method.agent_post.id,
      aws_api_gateway_integration.lambda_integration.id,
      aws_api_gateway_method.agent_options.id,
      aws_api_gateway_integration.agent_options.id,
      aws_api_gateway_resource.coach.id,
      aws_api_gateway_method.coach_get.id,
      aws_api_gateway_integration.coach_get.id,
      aws_api_gateway_method.coach_options.id,
      aws_api_gateway_integration.coach_options.id,
      aws_api_gateway_resource.teams.id,
      aws_api_gateway_method.teams_get.id,
      aws_api_gateway_method.teams_put.id,
      aws_api_gateway_integration.teams_get.id,
      aws_api_gateway_integration.teams_put.id,
      aws_api_gateway_method.teams_options.id,
      aws_api_gateway_integration.teams_options.id,
      aws_api_gateway_resource.chat.id,
      aws_api_gateway_method.chat_post.id,
      aws_api_gateway_integration.chat_post.id,
      aws_api_gateway_method.chat_options.id,
      aws_api_gateway_integration.chat_options.id,
      aws_api_gateway_resource.depth_chart.id,
      aws_api_gateway_method.depth_chart_get.id,
      aws_api_gateway_integration.depth_chart_lambda.id,
      aws_api_gateway_method.depth_chart_options.id,
      aws_api_gateway_integration.depth_chart_options.id,
      # Lambda function source code hashes - triggers redeployment on code changes
      # Note: unified_coach excluded to avoid circular dependency
      aws_lambda_function.draft_agent.source_code_hash,
      aws_lambda_function.coach.source_code_hash,
      aws_lambda_function.roster_management.source_code_hash,
      aws_lambda_function.chat_manager.source_code_hash,
      aws_lambda_function.depth_chart_api.source_code_hash
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage (existing)
resource "aws_api_gateway_stage" "demo" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "demo"

  # Optional: Add stage-level configuration
  xray_tracing_enabled = true

  # Optional: Add access logging
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}