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

resource "aws_dynamodb_table" "fantasy_football_team_roster" {
  name         = var.team_roster_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "team_id"

  attribute {
    name = "team_id"
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