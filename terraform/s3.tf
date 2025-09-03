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