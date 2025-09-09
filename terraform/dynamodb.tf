resource "aws_dynamodb_table" "fantasy_football_team_roster" {
  name         = var.team_roster_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "team_id"

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

resource "aws_dynamodb_table" "waiver_table" {
  name         = "${var.agent_name}-2025-waiver-table"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "player_season"

  attribute {
    name = "player_season"
    type = "S"
  }

  ttl {
    attribute_name = "updated_at"
    enabled        = false
  }

  tags = {
    Name        = "fantasy-players-table"
    Environment = "production"
  }
}

resource "aws_dynamodb_table" "fantasy_football_players" {
  name         = "fantasy-football-players"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "player_id"

  attribute {
    name = "player_id"
    type = "S"
  }

  attribute {
    name = "position"
    type = "S"
  }

  global_secondary_index {
    name            = "position-index"
    hash_key        = "position"
    projection_type = "ALL"
  }

  tags = {
    Name        = "fantasy-football-players"
    Environment = "production"
    Purpose     = "fantasy-football-ai-agent"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}