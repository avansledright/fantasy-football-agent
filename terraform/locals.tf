locals {
  lambda_zip_hash   = fileexists("${path.module}/lambda_function.zip") ? filemd5("${path.module}/lambda_function.zip") : ""
  requirements_hash = filemd5("lambda_code/requirements.txt")
  lambda_files      = fileset("${path.module}/lambda_code", "**/*")
  lambda_code_hash = md5(join("", [
    for file in local.lambda_files :
    filemd5("${path.module}/lambda_code/${file}")
  ]))
  layer_zip_name = "lambda_layer_${local.requirements_hash}.zip"
  # Some find and replace for the web interface:
  api_endpoint = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.demo.stage_name}"
  app_js_content = file("${path.module}/web-files/app.js.tpl")
  templated_app_js = replace(local.app_js_content, "$${api_endpoint}", local.api_endpoint)

}
