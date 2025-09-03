# Create the lambda layer zip file when requirements.txt changes
resource "null_resource" "lambda_layer_zip" {
  triggers = {
    requirements_hash = local.requirements_hash
  }

  provisioner "local-exec" {
    command = <<-EOT
        set -e
        echo "Creating lambda layer for requirements hash: ${local.requirements_hash}"

        # Create a temporary directory for building the layer
        mkdir -p ${path.module}/lambda_layer/python

        # Install dependencies to the python directory (required structure for layers)
        echo "Installing dependencies..."
        pip install -r lambda_code/requirements.txt -t ${path.module}/lambda_layer/python --python-version 3.12 --platform manylinux2014_aarch64 --only-binary=:all:

        # Create the zip file directly in the target location
        #echo "Creating zip file..."
        #cd ${path.module}/lambda_layer
        #zip -r "${path.module}/builds/lambda_layer.zip" python/
        # Cleanup
        #rm -rf ${path.module}/lambda_layer/
        echo "Layer zip created"
    EOT
  }
}

# Upload the layer zip to S3
resource "aws_s3_object" "lambda_layer_package" {
  depends_on = [null_resource.lambda_layer_zip]

  bucket = aws_s3_bucket.lambda_artifacts.id
  key    = "lambda_layer.zip"
  source = data.archive_file.lambda_layer.output_path

  lifecycle {
    create_before_destroy = true
  }
}

# Create the Lambda Layer
resource "aws_lambda_layer_version" "python_dependencies" {
  depends_on = [aws_s3_object.lambda_layer_package]

  layer_name               = "${var.agent_name}-lambda"
  s3_bucket                = aws_s3_bucket.lambda_artifacts.id
  s3_key                   = aws_s3_object.lambda_layer_package.key
  compatible_runtimes      = ["python3.12"]
  compatible_architectures = ["arm64"]

  description = "Python dependencies layer"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lambda_function" "draft_agent" {
  s3_bucket         = aws_s3_bucket.lambda_artifacts.id
  s3_key            = aws_s3_object.lambda_package.key
  s3_object_version = aws_s3_object.lambda_package.version_id
  function_name     = var.agent_name
  role              = aws_iam_role.lambda_role.arn
  handler           = "lambda_function.lambda_handler"
  runtime           = "python3.12"
  timeout           = 900
  memory_size       = 512
  architectures     = ["arm64"] #ARM 64 is required for Strands

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  layers = [
    aws_lambda_layer_version.python_dependencies.arn
  ]
  environment {
    variables = {
      # Use a different name since AWS_REGION is reserved
      BEDROCK_REGION   = var.aws_region
      BEDROCK_MODEL_ID = var.model_name
      LOG_LEVEL        = var.lambda_log_level
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.bedrock_access,
    aws_s3_object.lambda_package
  ]
}