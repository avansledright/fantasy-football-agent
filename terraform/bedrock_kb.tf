resource "aws_iam_role" "bedrock_kb_role" {
  name = "BedrockKnowledgeBaseExecutionRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      },
    ]
  })

  tags = {
    Project = "fantasy-football"
  }
}

resource "aws_iam_policy" "bedrock_kb_policy" {
  name = "BedrockKnowledgeBasePolicy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3vectors:QueryVectors"
        ]
        Resource = [
          aws_s3_bucket.knowledge_base.arn,
          "${aws_s3_bucket.knowledge_base.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.knowledge_base.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = "bedrock:InvokeModel"
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v1"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_kb_attach" {
  role       = aws_iam_role.bedrock_kb_role.name
  policy_arn = aws_iam_policy.bedrock_kb_policy.arn
}

# resource "aws_bedrockagent_knowledge_base" "my_fantasy_kb" {
#   name     = "fantasy-football-knowledge-base"
#   role_arn = aws_iam_role.bedrock_kb_role.arn

#   knowledge_base_configuration {
#     type = "VECTOR"
#     vector_knowledge_base_configuration {
#       embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v1"
#     }
#   }

#   storage_configuration {
#     type = "S3"
#   }

#   tags = {
#     Project = "fantasy-football"
#   }

#   depends_on = [
#     aws_iam_role_policy_attachment.bedrock_kb_attach
#   ]
# }

# resource "aws_bedrockagent_data_source" "rosters_data_source" {
#   knowledge_base_id = aws_bedrockagent_knowledge_base.my_fantasy_kb.id
#   name              = "rosters-s3-source"

#   data_source_configuration {
#     type = "S3"
#     s3_configuration {
#       bucket_arn         = aws_s3_bucket.knowledge_base.arn
#       inclusion_prefixes = ["rosters/"]
#     }
#   }

#   vector_ingestion_configuration {
#     chunking_configuration {
#       chunking_strategy = "FIXED_SIZE"
#       fixed_size_chunking_configuration {
#         max_tokens         = 512
#         overlap_percentage = 20
#       }
#     }
#   }
# }

# resource "aws_bedrockagent_data_source" "waivers_data_source" {
#   knowledge_base_id = aws_bedrockagent_knowledge_base.my_fantasy_kb.id
#   name              = "waivers-s3-source"

#   data_source_configuration {
#     type = "S3"
#     s3_configuration {
#       bucket_arn         = aws_s3_bucket.knowledge_base.arn
#       inclusion_prefixes = ["waivers/"]
#     }
#   }

#   vector_ingestion_configuration {
#     chunking_configuration {
#       chunking_strategy = "FIXED_SIZE"
#       fixed_size_chunking_configuration {
#         max_tokens         = 512
#         overlap_percentage = 20
#       }
#     }
#   }
# }

# resource "aws_bedrockagent_data_source" "player_stats_data_source" {
#   knowledge_base_id = aws_bedrockagent_knowledge_base.my_fantasy_kb.id
#   name              = "player-stats-s3-source"

#   data_source_configuration {
#     type = "S3"
#     s3_configuration {
#       bucket_arn         = aws_s3_bucket.knowledge_base.arn
#       inclusion_prefixes = ["player-stats/"]
#     }
#   }

#   vector_ingestion_configuration {
#     chunking_configuration {
#       chunking_strategy = "FIXED_SIZE"
#       fixed_size_chunking_configuration {
#         max_tokens         = 512
#         overlap_percentage = 20
#       }
#     }
#   }
# }