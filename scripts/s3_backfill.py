import boto3
import json
import time
from decimal import Decimal

# --- SCRIPT CONFIGURATION ---
AWS_REGION = "us-west-2"
LAMBDA_FUNCTION_NAME = "DynamoDBStreamToS3Processor"
TABLES_TO_BACKFILL = {
    "fantasy-football-players-updated": "arn:aws:dynamodb:us-west-2:481692562261:table/fantasy-football-players-updated/stream/2025-10-22T16:52:06.288",
    "fantasy-football-team-roster": "arn:aws:dynamodb:us-west-2:481692562261:table/fantasy-football-team-roster/stream/2025-10-21T19:05:51.383",
}
BATCH_SIZE = 100
# --- END SCRIPT CONFIGURATION ---

# Boto3 clients
dynamodb = boto3.client('dynamodb', region_name=AWS_REGION)
lambda_client = boto3.client('lambda', region_name=AWS_REGION)

# Custom JSON encoder to handle potential Decimal types if they appear.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def backfill_table(table_name, stream_arn):
    """Scans a DynamoDB table and invokes a Lambda for each batch of items."""
    print(f"\n--- Starting backfill for table: {table_name} ---")
    paginator = dynamodb.get_paginator('scan')
    
    item_batch = []
    total_items_scanned = 0
    total_batches_sent = 0

    try:
        for page in paginator.paginate(TableName=table_name):
            if not page.get('Items'):
                continue

            for item in page['Items']:
                total_items_scanned += 1
                
                stream_record = {
                    'eventName': 'INSERT',
                    'eventSourceARN': stream_arn,
                    'dynamodb': {
                        'NewImage': item
                    }
                }
                item_batch.append(stream_record)

                if len(item_batch) >= BATCH_SIZE:
                    invoke_lambda_with_batch(item_batch, table_name)
                    total_batches_sent += 1
                    item_batch = []

            print(f"  Scanned {total_items_scanned} items so far...")

        if item_batch:
            invoke_lambda_with_batch(item_batch, table_name)
            total_batches_sent += 1
        
        print(f"--- Finished backfill for {table_name} ---")
        print(f"  Total Items Scanned: {total_items_scanned}")
        print(f"  Total Batches Sent: {total_batches_sent}")

    except Exception as e:
        print(f"  [ERROR] An error occurred during the backfill for {table_name}: {e}")
        print("  Stopping backfill for this table.")

def invoke_lambda_with_batch(batch, table_name, is_retry=False):
    """Invokes the target Lambda and retries individual records on batch failure."""
    if not batch:
        return

    payload = {'Records': batch}
    
    # For single-item retries, print the specific ID
    if is_retry and len(batch) == 1:
        record_id = "UNKNOWN"
        try: # Try to find a primary key for better logging
            new_image = batch[0].get('dynamodb', {}).get('NewImage', {})
            record_id = new_image.get("player_id", {}).get("S") or \
                        new_image.get("team_id", {}).get("S") or \
                        new_image.get("player_season", {}).get("S")
        except:
            pass # Ignore if we can't find it
        print(f"  Retrying single item '{record_id}' from '{table_name}'...")
    else:
        print(f"  Sending batch of {len(batch)} items from '{table_name}' to Lambda...")
    
    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload, cls=DecimalEncoder)
        )
        
        response_payload_raw = response['Payload'].read()
        response_payload = json.loads(response_payload_raw)
        
        if response.get('StatusCode') != 200 or 'errorMessage' in response_payload:
            print(f"    [FATAL] Lambda invocation returned a major error for this batch.")
            print(f"    Status Code: {response.get('StatusCode')}")
            print(f"    Response Payload: {response_payload}")
            
            # If a batch fails and it's NOT already a retry, break it down and retry individually.
            if not is_retry and len(batch) > 1:
                print("    Attempting to process records individually to find the failure...")
                for record in batch:
                    invoke_lambda_with_batch([record], table_name, is_retry=True)
            return

        lambda_body = json.loads(response_payload.get('body', '{}'))
        failures = lambda_body.get("failureCount", 0)

        if failures > 0:
            print(f"    [WARNING] Lambda reported {failures} failures for this batch.")
            failed_records = lambda_body.get("failedRecords", [])
            for failed_record in failed_records:
                print(f"      - Failed Record ID: {failed_record.get('recordId')}")
                print(f"        Error: {failed_record.get('error')}")

            # If a batch reports failures and it's NOT already a retry, break it down.
            if not is_retry and len(batch) > 1:
                print("    Attempting to process records individually to find the exact failure...")
                for record in batch:
                     invoke_lambda_with_batch([record], table_name, is_retry=True)
        else:
            success_count = lambda_body.get("successCount", len(batch))
            print(f"    ...Batch processed successfully. {success_count} records written to S3.")

        time.sleep(0.5)

    except Exception as e:
        print(f"    [FATAL ERROR] Failed to invoke Lambda function or parse response: {e}")
        if not is_retry: # Avoid raising during individual retries to allow script to continue
            raise

if __name__ == "__main__":
    print("Starting DynamoDB to S3 Backfill Process...")
    for table, arn in TABLES_TO_BACKFILL.items():
        backfill_table(table, arn)
    print("\nAll backfill tasks are complete.")