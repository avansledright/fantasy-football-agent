data "aws_iam_policy_document" "lambda_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dynamodb_stream_to_s3_lambda_role" {
  name               = "DynamoStreamToS3LambdaRole"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role_policy.json
}

data "aws_iam_policy_document" "dynamodb_stream_to_s3_lambda_policy" {
  # Permissions to read from DynamoDB Streams
  statement {
    actions = [
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:DescribeStream",
      "dynamodb:ListStreams"
    ]
    # Grant access to all streams in the account/region for simplicity,
    # or scope down using specific table stream ARNs
    resources = ["arn:aws:dynamodb:*:*:table/*/stream/*"]
  }

  # Permissions to write logs to CloudWatch
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  # Permissions to write to the target S3 bucket
  statement {
    actions = [
      "s3:PutObject"
    ]
    resources = [
      aws_s3_bucket.knowledge_base.arn,
      "${aws_s3_bucket.knowledge_base.arn}/*" # Allow writing objects within the bucket
    ]
  }
}

resource "aws_iam_policy" "dynamodb_stream_to_s3_lambda_policy" {
  name   = "DynamoStreamToS3LambdaPolicy"
  policy = data.aws_iam_policy_document.dynamodb_stream_to_s3_lambda_policy.json
}

resource "aws_iam_role_policy_attachment" "dynamodb_stream_to_s3_lambda_attach" {
  role       = aws_iam_role.dynamodb_stream_to_s3_lambda_role.name
  policy_arn = aws_iam_policy.dynamodb_stream_to_s3_lambda_policy.arn
}

### CODE FOR LAMBDA ###
data "archive_file" "dynamo_stream_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_function_payload.zip"
  source {
    content = <<-EOT
import json
import boto3
import os
import datetime
from decimal import Decimal

# Helper to convert DynamoDB structure to plain Python types
def dynamodb_to_dict(item):
    if not item: return None
    result = {}
    for key, value_dict in item.items():
        value_type = list(value_dict.keys())[0]
        value = value_dict[value_type]
        if value_type == 'S': result[key] = str(value)
        elif value_type == 'N':
            d = Decimal(value)
            result[key] = int(d) if d % 1 == 0 else float(d)
        elif value_type == 'BOOL': result[key] = bool(value)
        elif value_type == 'NULL': result[key] = None
        elif value_type == 'M': result[key] = dynamodb_to_dict(value)
        elif value_type == 'L': result[key] = [dynamodb_to_dict({'temp': v})['temp'] for v in value]
        else: result[key] = str(value)
    return result

# --- Lambda Handler ---
s3 = boto3.client('s3')
bucket_name = os.environ.get('TARGET_S3_BUCKET')
roster_table_name = os.environ.get('ROSTER_TABLE_NAME')
player_table_name = os.environ.get('PLAYER_TABLE_NAME')

table_prefixes = {
    roster_table_name: 'rosters/',
    player_table_name: 'player-stats/'
}

def lambda_handler(event, context):
    success_count = 0
    failed_records = []

    if not bucket_name:
        raise ValueError("FATAL: TARGET_S3_BUCKET environment variable not set.")

    for record in event.get('Records', []):
        record_id = "UNKNOWN"
        try:
            dynamodb_data = record.get('dynamodb')
            if not isinstance(dynamodb_data, dict):
                raise ValueError("Record is missing 'dynamodb' dictionary.")
            
            new_image_ddb = dynamodb_data.get('NewImage')
            event_name = record.get('eventName')
            table_arn = record.get('eventSourceARN', 'unknown_arn')
            table_name = table_arn.split('/')[1] if '/' in table_arn else 'unknown_table'
            
            if new_image_ddb:
                record_id = new_image_ddb.get("player_id", {}).get("S") or \
                            new_image_ddb.get("team_id", {}).get("S") or \
                            new_image_ddb.get("player_season", {}).get("S") or \
                            record.get('eventID', 'UNKNOWN')

            if not new_image_ddb or event_name == 'REMOVE':
                continue

            item_dict = dynamodb_to_dict(new_image_ddb)
            if not item_dict:
                 raise ValueError("Failed to convert DynamoDB item to dictionary.")

            # --- Simplified Logic: Dump the entire object as a formatted JSON string ---
            file_content = json.dumps(item_dict, indent=2)
            
            # Determine primary key for the filename
            primary_key_value = "unknown_item"
            if table_name == roster_table_name:
                primary_key_value = item_dict.get('team_id', record_id)
            elif table_name == player_table_name:
                primary_key_value = item_dict.get('player_id', record_id).replace('#','_').replace('/','_')
            else:
                raise ValueError(f"Unrecognized table name: {table_name}")

            prefix = table_prefixes.get(table_name, 'unknown_table_data/')
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
            s3_key = f"{prefix}{primary_key_value}_{timestamp}.txt" # Keep .txt extension

            s3.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_content.encode('utf-8'),
                ContentType='text/plain' # Treat the JSON string as plain text for ingestion
            )
            success_count += 1

        except Exception as e:
            error_message = f"Error processing record ID {record_id}: {str(e)}"
            print(error_message)
            failed_records.append({"recordId": record_id, "error": error_message})

    failure_count = len(failed_records)
    print(f"Processing complete. Success: {success_count}, Failures: {failure_count}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            "message": f"Processed {success_count + failure_count} records.",
            "successCount": success_count,
            "failureCount": failure_count,
            "failedRecords": failed_records
        })
    }


EOT
    filename    = "lambda_function.py"
  }
}


### END LAMBDA CODE ###

resource "aws_lambda_function" "dynamodb_stream_processor" {
  filename         = data.archive_file.dynamo_stream_lambda_zip.output_path
  function_name    = "DynamoDBStreamToS3Processor"
  role             = aws_iam_role.dynamodb_stream_to_s3_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.dynamo_stream_lambda_zip.output_base64sha256
  runtime          = "python3.12"

  environment {
    variables = {
      TARGET_S3_BUCKET    = aws_s3_bucket.knowledge_base.id
      ROSTER_TABLE_NAME   = aws_dynamodb_table.fantasy_football_team_roster.name 
      PLAYER_TABLE_NAME   = aws_dynamodb_table.fantasy_football_player_data.name
    }
  }

  # Increase timeout if processing large batches takes time
  timeout = 60
}

resource "aws_lambda_event_source_mapping" "roster_stream_mapping" {
  event_source_arn  = aws_dynamodb_table.fantasy_football_team_roster.stream_arn
  function_name     = aws_lambda_function.dynamodb_stream_processor.arn
  starting_position = "LATEST" 
  batch_size        = 100      
}

resource "aws_lambda_event_source_mapping" "players_stream_mapping" {
  event_source_arn  = aws_dynamodb_table.fantasy_football_player_data.stream_arn
  function_name     = aws_lambda_function.dynamodb_stream_processor.arn
  starting_position = "LATEST"
  batch_size        = 100
}