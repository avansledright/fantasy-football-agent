locals {
  lambda_zip_hash   = fileexists("${path.module}/lambda_function.zip") ? filemd5("${path.module}/lambda_function.zip") : ""
  requirements_hash = filemd5("lambda_code/requirements.txt")
  lambda_files      = fileset("${path.module}/lambda_code", "**/*")
  lambda_code_hash = md5(join("", [
    for file in local.lambda_files :
    filemd5("${path.module}/lambda_code/${file}")
  ]))
  layer_zip_name = "lambda_layer_${local.requirements_hash}.zip"
}