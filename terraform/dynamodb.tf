resource "aws_dynamodb_table" "fantasy_player_data" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "player_id"

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

resource "aws_dynamodb_table" "season_stats" {
  name         = var.stats_table
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "player_season"
  range_key = "week"

  attribute {
    name = "player_season"
    type = "S"
  }

  attribute {
    name = "week"
    type = "N"
  }

  attribute {
    name = "position"
    type = "S"
  }

  attribute {
    name = "season"
    type = "N"
  }

  global_secondary_index {
    name            = "position-season-index"
    hash_key        = "position"
    range_key       = "season"
    projection_type = "ALL"
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

resource "aws_dynamodb_table" "season_stats_2025" {
  name         = var.stats_table_2025
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "player_season"
  range_key = "week"

  attribute {
    name = "player_season"
    type = "S"
  }

  attribute {
    name = "week"
    type = "N"
  }

  attribute {
    name = "position"
    type = "S"
  }

  attribute {
    name = "season"
    type = "N"
  }

  global_secondary_index {
    name            = "position-season-index"
    hash_key        = "position"
    range_key       = "season"
    projection_type = "ALL"
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