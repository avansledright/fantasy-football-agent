variable "aws_region" {
  type = string
  description = "the aws region to deploy into"
  default = "us-west-2"
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
  type = string
}

variable "lambda_log_level" {
  description = "The logging level for the lambda function"
  type        = string
  default     = "INFO"
}

variable "api_gateway_integration_timeout" {
  description = "The timeout of the API Gateway integration in MS"
  type = number
  default = 29000
}

variable "team_roster_table_name" {
  description = "Name of the team table"
  default = "fantasy-football-team-roster"
}