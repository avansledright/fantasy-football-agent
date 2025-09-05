variable "aws_region" {
  type        = string
  description = "the aws region to deploy into"
  default     = "us-west-2"
}

variable "table_name" {
  description = "DynamoDB table name"
  type        = string
  default     = "2025-2026-fantasy-football-player-data"
}

variable "agent_name" {
  description = "Name of the Strands agent demo"
  type        = string
}

variable "model_name" {
  description = "ID of the model to be used for the agent"
  type        = string
}

variable "lambda_log_level" {
  description = "The logging level for the lambda function"
  type        = string
  default     = "INFO"
}

variable "api_gateway_integration_timeout" {
  description = "The timeout of the API Gateway integration in MS"
  type        = number
  default     = 29000
}

variable "team_roster_table_name" {
  description = "Name of the team table"
  default     = "fantasy-football-team-roster"
}

variable "stats_table" {
  description = "Name of the stats table"
  default     = "fantasy-football-2024-stats"
}

variable "coach_function_name" {
  description = "Name of the coach function"
  default     = "fantasy-football-coach-lambda"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for static web hosting"
  type        = string
  default     = "fantasy-football-web-app"
}

# Cloudfront things
variable "cloudfront_price_class" {
  description = "CloudFront price class - using cheapest option for cost optimization"
  type        = string
  default     = "PriceClass_100"  # Only US, Canada, Europe edge locations (cheapest)
  
  validation {
    condition = contains([
      "PriceClass_All",
      "PriceClass_200", 
      "PriceClass_100"
    ], var.cloudfront_price_class)
    error_message = "Price class must be PriceClass_All, PriceClass_200, or PriceClass_100."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

# Cost optimization settings
variable "enable_cloudfront_logging" {
  description = "Enable CloudFront access logging (adds S3 storage costs)"
  type        = bool
  default     = false  # Disabled for cost optimization
}

variable "cache_ttl_static_assets" {
  description = "TTL for static assets in seconds (longer = more cost effective)"
  type        = number
  default     = 31536000  # 1 year for maximum caching efficiency
}

variable "cache_ttl_api_responses" {
  description = "TTL for API responses in seconds (0 = no caching for dynamic content)"
  type        = number
  default     = 0  # No API caching to ensure data freshness
}

variable "stats_table_2025" {
  description = "name of the 2025 stats table"
  default = "fantasy-football-2025-stats"
}

variable "lambda_function_name" {
  description = "Name of the Stats Scraper Lambda function"
  type        = string
  default     = "fantasy-football-stats-scraper"
}