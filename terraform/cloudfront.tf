# CloudFront Origin Access Control for S3
resource "aws_cloudfront_origin_access_control" "s3_oac" {
  name                              = "${var.agent_name}-s3-oac"
  description                       = "OAC for Fantasy Football S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}


# CloudFront Distribution
resource "aws_cloudfront_distribution" "fantasy_football_cdn" {
  comment             = "Fantasy Football AI Coach CDN"
  default_root_object = "index.html"
  enabled             = true
  is_ipv6_enabled     = true
  price_class         = var.cloudfront_price_class

  # S3 Origin
  origin {
    domain_name              = aws_s3_bucket.fantasy_football_web.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.fantasy_football_web.bucket}"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3_oac.id
  }

  # API Gateway Origin - FIXED
  origin {
    domain_name = "${aws_api_gateway_rest_api.main.id}.execute-api.${var.aws_region}.amazonaws.com"
    origin_id   = "API-${aws_api_gateway_rest_api.main.name}"
    origin_path = "/${aws_api_gateway_stage.demo.stage_name}"

    custom_origin_config {
      http_port              = 443
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-Forwarded-Host"
      value = aws_api_gateway_rest_api.main.id
    }
  }

  # Default cache behavior (for web assets)
  default_cache_behavior {
    target_origin_id       = "S3-${aws_s3_bucket.fantasy_football_web.bucket}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      headers      = ["Origin", "Access-Control-Request-Headers", "Access-Control-Request-Method"]

      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400    # 24 hours
    max_ttl     = 31536000 # 1 year
  }

  # Cache behavior for API calls
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "API-${aws_api_gateway_rest_api.main.name}"
    viewer_protocol_policy = "https-only"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Content-Type", "Origin", "Access-Control-Request-Headers", "Access-Control-Request-Method"]

      cookies {
        forward = "all"
      }
    }

    min_ttl     = 0
    default_ttl = 0     # Don't cache API responses by default
    max_ttl     = 86400 # 24 hours max
  }

  # Cache behavior for static assets with longer TTL
  ordered_cache_behavior {
    path_pattern           = "*.css"
    target_origin_id       = "S3-${aws_s3_bucket.fantasy_football_web.bucket}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 31536000 # 1 year
    max_ttl     = 31536000 # 1 year
  }

  # Cache behavior for JavaScript files
  ordered_cache_behavior {
    path_pattern           = "*.js"
    target_origin_id       = "S3-${aws_s3_bucket.fantasy_football_web.bucket}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400  # 24 hours (shorter for JS due to API endpoint changes)
    max_ttl     = 604800 # 1 week
  }

  # Geographic restrictions
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # SSL Certificate
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# Response Headers Policy for Security
resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name    = "${var.agent_name}-security-headers"
  comment = "Security headers for Fantasy Football app"

  cors_config {
    access_control_allow_credentials = false

    access_control_allow_headers {
      items = ["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"]
    }

    access_control_allow_methods {
      items = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"]
    }

    access_control_allow_origins {
      items = ["*"]
    }

    access_control_expose_headers {
      items = ["Date", "ETag"]
    }

    access_control_max_age_sec = 3600
    origin_override            = false
  }

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      override                   = true
    }

    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
  }
}

# S3 bucket for CloudFront access logs
resource "aws_s3_bucket" "cloudfront_logs" {
  bucket        = "${var.agent_name}-cloudfront-logs-${random_id.bucket_suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    id     = "delete_old_logs"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = 3
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "fantasy_football_web_cloudfront" {
  bucket = aws_s3_bucket.fantasy_football_web.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PublicReadGetObject"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.fantasy_football_web.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.fantasy_football_cdn.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_cloudfront_distribution.fantasy_football_cdn]
}

# CloudFront Invalidation Lambda (for cache busting on deployments)
resource "aws_iam_role" "cloudfront_invalidation" {
  name = "${var.agent_name}-cloudfront-invalidation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "cloudfront_invalidation" {
  name = "${var.agent_name}-cloudfront-invalidation-policy"
  role = aws_iam_role.cloudfront_invalidation.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation"
        ]
        Resource = aws_cloudfront_distribution.fantasy_football_cdn.arn
      }
    ]
  })
}

# Lambda function for CloudFront invalidation
resource "aws_lambda_function" "cloudfront_invalidation" {
  filename      = data.archive_file.cloudfront_invalidation_zip.output_path
  function_name = "${var.agent_name}-cloudfront-invalidation"
  role          = aws_iam_role.cloudfront_invalidation.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = 60

  source_code_hash = data.archive_file.cloudfront_invalidation_zip.output_base64sha256

  environment {
    variables = {
      DISTRIBUTION_ID = aws_cloudfront_distribution.fantasy_football_cdn.id
    }
  }
}

# Archive the invalidation function code
data "archive_file" "cloudfront_invalidation_zip" {
  type        = "zip"
  output_path = "${path.module}/cloudfront_invalidation.zip"

  source {
    content  = <<EOF
import boto3
import json
import os
import time

def lambda_handler(event, context):
    """
    Lambda function to invalidate CloudFront cache
    """
    try:
        cloudfront = boto3.client('cloudfront')
        distribution_id = os.environ['DISTRIBUTION_ID']
        
        # Create invalidation
        response = cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 3,
                    'Items': [
                        '/*',
                        '/index.html',
                        '/app.js'
                    ]
                },
                'CallerReference': f"terraform-{int(time.time())}"
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Invalidation created successfully',
                'invalidation_id': response['Invalidation']['Id']
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
EOF
    filename = "lambda_function.py"
  }
}

# CloudWatch Log Group for invalidation Lambda
resource "aws_cloudwatch_log_group" "cloudfront_invalidation_logs" {
  name              = "/aws/lambda/${aws_lambda_function.cloudfront_invalidation.function_name}"
  retention_in_days = 14
}

# Outputs
output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.fantasy_football_cdn.id
  description = "CloudFront Distribution ID"
}

output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.fantasy_football_cdn.domain_name
  description = "CloudFront Distribution Domain Name"
}

output "cloudfront_hosted_zone_id" {
  value       = aws_cloudfront_distribution.fantasy_football_cdn.hosted_zone_id
  description = "CloudFront Distribution Hosted Zone ID"
}

output "website_url" {
  value       = "https://${aws_cloudfront_distribution.fantasy_football_cdn.domain_name}"
  description = "Website URL"
}

output "invalidation_lambda_arn" {
  value       = aws_lambda_function.cloudfront_invalidation.arn
  description = "CloudFront Invalidation Lambda ARN"
}