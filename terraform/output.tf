# Outputs
output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = "https://${aws_api_gateway_rest_api.strands_demo.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.demo.stage_name}/agent"
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.strands_demo.function_name
}

output "test_command" {
  description = "Test command for the Strands agent"
  value       = <<-EOT
    curl -X POST "https://${aws_api_gateway_rest_api.strands_demo.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.demo.stage_name}/agent" \
         -H "Content-Type: application/json" \
         -d '{"prompt": "Return the weather for Chicago Illinois"}'
  EOT
}