resource "aws_s3_bucket" "lambda_artifacts" {
  bucket        = "${var.agent_name}-${random_id.bucket_suffix.hex}"
  force_destroy = true
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Upload Lambda deployment package to S3
resource "aws_s3_object" "lambda_package" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  key    = "lambda_function.zip"
  source = data.archive_file.lambda_zip.output_path
  etag   = filemd5(data.archive_file.lambda_zip.output_path)
  provisioner "local-exec" {
    command = "rm -f ${path.module}/lambda_function-${local.lambda_code_hash}.zip"
    when    = create
  }
}

# Upload Lambda deployment package to S3
resource "aws_s3_object" "coach_lambda_package" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  key    = "coach_lambda_function.zip"
  source = data.archive_file.coach_lambda_zip.output_path
  etag   = filemd5(data.archive_file.coach_lambda_zip.output_path)
  provisioner "local-exec" {
    command = "rm -f ${path.module}/builds/coach_lambda-${local.lambda_code_hash}.zip"
    when    = create
  }
}

resource "aws_s3_bucket" "fantasy_football_web" {
  bucket = var.s3_bucket_name
}

resource "aws_s3_bucket_versioning" "fantasy_football_web" {
  bucket = aws_s3_bucket.fantasy_football_web.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_website_configuration" "fantasy_football_web" {
  bucket = aws_s3_bucket.fantasy_football_web.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

resource "aws_s3_bucket_public_access_block" "fantasy_football_web" {
  bucket = aws_s3_bucket.fantasy_football_web.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# S3 bucket policy for public read access
resource "aws_s3_bucket_policy" "fantasy_football_web" {
  bucket = aws_s3_bucket.fantasy_football_web.id
  depends_on = [aws_s3_bucket_public_access_block.fantasy_football_web]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.fantasy_football_web.arn}/*"
      }
    ]
  })
}

# Upload static files
resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.fantasy_football_web.id
  key          = "index.html"
  source       = "${path.module}/web-files/index.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/web-files/index.html")
}

resource "aws_s3_object" "styles_css" {
  bucket       = aws_s3_bucket.fantasy_football_web.id
  key          = "styles.css"
  source       = "${path.module}/web-files/styles.css"
  content_type = "text/css"
  etag         = filemd5("${path.module}/web-files/styles.css")
}

# Upload templated app.js file
resource "aws_s3_object" "app_js" {
  bucket       = aws_s3_bucket.fantasy_football_web.id
  key          = "app.js"
  content      = local.templated_app_js
  content_type = "application/javascript"
  etag         = md5(local.templated_app_js)
}