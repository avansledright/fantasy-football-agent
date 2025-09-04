import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    """
    Handle roster management operations
    """
    try:
        http_method = event['httpMethod']
        
        # Handle CORS preflight requests
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, PUT, POST, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key, X-Amz-Security-Token'
                },
                'body': ''
            }
        
        if http_method == 'GET':
            return get_team_roster(event)
        elif http_method == 'PUT':
            return update_team_roster(event)
        else:
            return {
                'statusCode': 405,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }

def get_team_roster(event):
    """
    Get team roster from DynamoDB
    """
    try:
        # Get team_id from query parameters
        query_params = event.get('queryStringParameters') or {}
        team_id = query_params.get('team_id')
        
        if not team_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'team_id parameter is required'})
            }
        
        # Get team data from DynamoDB
        response = table.get_item(
            Key={'team_id': team_id}
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Team not found'})
            }
        
        team_data = response['Item']
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps(team_data, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error getting team roster: {str(e)}")
        raise

def update_team_roster(event):
    """
    Update team roster in DynamoDB
    """
    try:
        # Parse request body
        body = json.loads(event['body'])
        team_id = body.get('team_id')
        
        if not team_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'team_id is required in request body'})
            }
        
        # Prepare update data
        update_data = {
            'team_id': team_id,
            'last_updated': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Add optional fields if provided
        if 'league_id' in body:
            update_data['league_id'] = body['league_id']
        if 'owner' in body:
            update_data['owner'] = body['owner']
        if 'players' in body:
            update_data['players'] = body['players']
        
        # Update item in DynamoDB
        table.put_item(Item=update_data)
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'Team roster updated successfully',
                'team_id': team_id
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        print(f"Error updating team roster: {str(e)}")
        raise