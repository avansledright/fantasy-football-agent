resource "aws_dynamodb_table" "fantasy_player_data" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "player_id"

  attribute {
    name = "player_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project     = "fantasy-football"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}