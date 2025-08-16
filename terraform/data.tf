data "aws_caller_identity" "current" {}

# Create Lambda Code ZIP file
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_code"
  output_path = "${path.module}/builds/lambda_function-${local.lambda_code_hash}.zip"
}

# Create Lambda Code ZIP file
data "archive_file" "lambda_layer" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_layer"
  output_path = "${path.module}/builds/lambda_layer-${local.requirements_hash}.zip"
  depends_on = [ null_resource.lambda_layer_zip ]
}
