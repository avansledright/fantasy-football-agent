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
    Get team roster from DynamoDB and attach weekly fantasy points if available
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        team_id = query_params.get('team_id')
        week = query_params.get('week')

        if not team_id:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'team_id parameter is required'})
            }

        response = table.get_item(Key={'team_id': team_id})
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Team not found'})
            }

        team_data = response['Item']

        # If week provided, enrich players with final scores using batch operations
        if week and 'players' in team_data and team_data['players']:
            try:
                week_int = int(week)
                season = 2025  # or pull dynamically if needed
                
                # Get all stats in batch operations for efficiency
                player_stats = get_player_stats_batch(team_data['players'], season, week_int)
                
                # Attach stats to players
                for player in team_data['players']:
                    player_name = player.get('name')
                    if player_name and player_name in player_stats:
                        stats = player_stats[player_name]
                        player['final_score'] = float(stats.get('fantasy_points', 0))
                        player['opponent'] = stats.get('opponent')
                    else:
                        # Ensure all players have final_score field for consistency
                        player['final_score'] = 0.0
                        
            except ValueError:
                print(f"Invalid week number: {week}")
            except Exception as e:
                print(f"Error fetching player stats: {str(e)}")
                # Continue without stats rather than failing

        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps(team_data, default=decimal_default)
        }

    except Exception as e:
        print(f"Error getting team roster: {str(e)}")
        raise

def get_player_stats_batch(players, season, week):
    """
    Efficiently fetch player stats using batch operations
    """
    if not players:
        return {}
    
    stats_table = dynamodb.Table(os.environ['PLAYER_STATS_TABLE'])
    player_stats = {}
    
    # Prepare batch get items - DynamoDB batch_get_item supports up to 100 items
    batch_size = 100
    player_names = [p.get('name') for p in players if p.get('name')]
    
    for i in range(0, len(player_names), batch_size):
        batch_players = player_names[i:i + batch_size]
        
        # Build request items for batch operation
        request_items = {
            os.environ['PLAYER_STATS_TABLE']: {
                'Keys': [
                    {
                        'player_season': f"{player_name}#{season}",
                        'week': week
                    }
                    for player_name in batch_players
                ]
            }
        }
        
        try:
            response = dynamodb.batch_get_item(RequestItems=request_items)
            
            # Process responses
            if os.environ['PLAYER_STATS_TABLE'] in response.get('Responses', {}):
                for item in response['Responses'][os.environ['PLAYER_STATS_TABLE']]:
                    # Extract player name from player_season key
                    player_season = item.get('player_season', '')
                    if '#' in player_season:
                        player_name = player_season.split('#')[0]
                        player_stats[player_name] = item
            
            # Handle unprocessed items (due to throttling, etc.)
            unprocessed = response.get('UnprocessedKeys', {})
            retry_count = 0
            max_retries = 3
            
            while unprocessed and retry_count < max_retries:
                print(f"Retrying unprocessed items, attempt {retry_count + 1}")
                response = dynamodb.batch_get_item(RequestItems=unprocessed)
                
                if os.environ['PLAYER_STATS_TABLE'] in response.get('Responses', {}):
                    for item in response['Responses'][os.environ['PLAYER_STATS_TABLE']]:
                        player_season = item.get('player_season', '')
                        if '#' in player_season:
                            player_name = player_season.split('#')[0]
                            player_stats[player_name] = item
                
                unprocessed = response.get('UnprocessedKeys', {})
                retry_count += 1
                
        except Exception as e:
            print(f"Error in batch operation for players {batch_players}: {str(e)}")
            # Fall back to individual queries for this batch
            for player_name in batch_players:
                try:
                    individual_response = stats_table.get_item(
                        Key={
                            'player_season': f"{player_name}#{season}",
                            'week': week
                        }
                    )
                    if 'Item' in individual_response:
                        player_stats[player_name] = individual_response['Item']
                except Exception as individual_error:
                    print(f"Error fetching stats for {player_name}: {str(individual_error)}")
    
    return player_stats

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

def cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }