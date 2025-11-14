resource "aws_s3_bucket" "lambda_artifacts" {
  bucket        = "${var.agent_name}-${random_id.bucket_suffix.hex}"
  force_destroy = true
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "knowledge_base" {
  bucket        = "${var.agent_name}-knowledge-base-${random_id.bucket_suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "knowledge_base" {
  bucket = aws_s3_bucket.knowledge_base.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  versioning_configuration {
    status = "Enabled"
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

# Upload static files
resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.fantasy_football_web.id
  key          = "index.html"
  source       = "${path.module}/web-files/index.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/web-files/index.html")
}

resource "aws_s3_object" "index2_html" {
  bucket       = aws_s3_bucket.fantasy_football_web.id
  key          = "index2.html"
  source       = "${path.module}/web-files/index2.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/web-files/index2.html")
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

# Upload templated unified-coach.js file
resource "aws_s3_object" "unified_coach_js" {
  bucket       = aws_s3_bucket.fantasy_football_web.id
  key          = "unified-coach.js"
  content      = local.templated_unified_coach_js
  content_type = "application/javascript"
  etag         = md5(local.templated_unified_coach_js)
}

resource "aws_s3_object" "js_files" {
  for_each = fileset("${path.module}/web-files", "*.js")
  
  bucket       = aws_s3_bucket.fantasy_football_web.id
  key          = each.value
  source       = "${path.module}/web-files/${each.value}"
  content_type = "application/javascript"
  etag         = filemd5("${path.module}/web-files/${each.value}")
}


resource "null_resource" "invalidate_cloudfront" {
  depends_on = [
    aws_s3_object.index_html,
    aws_s3_object.index2_html,
    aws_s3_object.styles_css,
    aws_s3_object.app_js,
    aws_s3_object.unified_coach_js,
    aws_s3_object.js_files
  ]

  triggers = {
    index_etag         = aws_s3_object.index_html.etag
    index2_etag        = aws_s3_object.index2_html.etag
    css_etag           = aws_s3_object.styles_css.etag
    js_etag            = aws_s3_object.app_js.etag
    unified_coach_etag = aws_s3_object.unified_coach_js.etag
    js_files           = join(",", [for obj in aws_s3_object.js_files : obj.etag])
  }

  provisioner "local-exec" {
    command = <<EOT
      aws lambda invoke \
        --function-name ${aws_lambda_function.cloudfront_invalidation.function_name} \
        --payload '{}' \
        response.json
    EOT
  }
}

