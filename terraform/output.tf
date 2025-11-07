# Outputs
output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.demo.stage_name}/agent"
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.draft_agent.function_name
}

output "knowledge_base_bucket" {
  description = "KB Bucket"
  value = aws_s3_bucket.knowledge_base.id
}

output "website_endpoint" {
  value = aws_s3_bucket_website_configuration.fantasy_football_web.website_endpoint
}

output "bucket_name" {
  value = aws_s3_bucket.fantasy_football_web.bucket
}

output "depth_chart_api_url" {
  description = "Depth Chart API endpoint"
  value       = "${aws_api_gateway_stage.demo.invoke_url}/depth-chart"
}