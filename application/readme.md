# Fantasy Football Draft CLI Tool

An interactive command-line tool for managing fantasy football snake drafts with AI-powered recommendations. This tool helps you track your draft picks, manage your roster, and get intelligent recommendations during your draft.

## Features

- **Snake Draft Logic**: Automatically calculates pick order for snake-style drafts
- **AI Recommendations**: Get intelligent player suggestions based on team needs and league context
- **Interactive Mode**: Real-time draft management with simple commands
- **Session Persistence**: Save and resume draft sessions
- **Player Database**: Integrated with AWS DynamoDB for comprehensive player data
- **Roster Management**: Track your team composition across all positions
- **Draft Board Visualization**: See recent picks and upcoming turns

## Prerequisites

- Python 3.8+
- AWS credentials configured (for DynamoDB access)
- Internet connection (for AI recommendations API)

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS credentials (one of the following):
   - AWS CLI: `aws configure`
   - Environment variables: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
   - IAM role (if running on EC2)

## Quick Start

### Starting a New Draft

```bash
# Start a new 8-team PPR draft with pick #3
python v2.py start --league-size 8 --your-pick 3 --scoring ppr

# Start a 12-team standard scoring draft with pick #7
python v2.py start --league-size 12 --your-pick 7 --scoring standard
```

### Interactive Draft Mode

```bash
# Enter interactive mode (recommended)
python v2.py interactive
```

In interactive mode, you can use these commands:

- **`next`** - Get AI recommendation for your pick
- **`player_name`** - Draft a player (auto-detects position)
- **`def [team_name]`** - Draft a defense (e.g., "def Buffalo")
- **`quit`** - Exit interactive mode

### Other Commands

```bash
# View draft board and recent picks
python v2.py board

# Check your roster and team status
python v2.py status

# Get AI recommendation for current pick
python v2.py next

# Manually add a pick
python v2.py add-pick --player "Josh Allen" --position QB --team 5

# Reset and start over
python v2.py reset
```

## How It Works

### Draft Structure

- **17 rounds** per team (standard fantasy league format)
- **Snake draft order**: Picks reverse direction each round
- **Position limits**: QB(3), RB(6), WR(6), TE(3), K(2), DST(2), FLEX(1), BENCH(6)
- **Starter requirements**: QB(1), RB(2), WR(2), TE(1), K(1), DST(1), FLEX(1)

### Player Database

The tool connects to a DynamoDB table containing:
- **2025 projections**: Fantasy point projections for the upcoming season
- **2024 actuals**: Historical performance data
- **Player metadata**: Names, positions, teams, rankings

### AI Recommendations

The recommendation engine considers:
- **Team needs**: Missing starter positions get priority
- **League context**: Scoring format (PPR/Standard) and league size
- **Available players**: Excludes already drafted players
- **Value-based drafting**: Balances positional scarcity with player quality

### Session Management

Draft sessions are automatically saved to `draft_session.json` and include:
- Your current roster
- All draft picks with timestamps
- League settings and draft position
- Current pick number and turn order

## Interactive Mode Walkthrough

1. **Start the draft**: `python v2.py start --league-size 12 --your-pick 5`
2. **Enter interactive mode**: `python v2.py interactive`
3. **When it's your turn**: Type `next` to get a recommendation
4. **Draft a player**: Type the player's name (e.g., "Christian McCaffrey")
5. **Draft a defense**: Type `def [team]` (e.g., "def San Francisco")
6. **Other team picks**: Enter other teams' picks to keep the draft moving
7. **Check status**: The tool shows your roster and upcoming picks

## Example Session

```bash
$ python v2.py start --league-size 12 --your-pick 5 --scoring ppr
🏈 New 12-team PPR snake draft started!
🎯 Your draft position: #5
📋 17-round draft format

$ python v2.py interactive
🎯 INTERACTIVE DRAFT MODE
Commands: 'next' (get recommendation), 'def [team]' (draft DST), 'quit' (exit)

🎯 YOUR TURN - Pick #5 (Round 1.5): next

🤖 Getting recommendation for YOUR pick #5 (Round 1.5)...
============================================================
🤖 AI RECOMMENDATION:
============================================================
🏈 RECOMMENDED: Christian McCaffrey (RB) - SF
📊 285.4 PPR points (16.8 PPG)
💭 Elite RB1 with proven track record. Excellent PPR value.

📋 ALTERNATIVES:
   1. Ja'Marr Chase (WR, CIN) - 268.3 pts
   2. Justin Jefferson (WR, MIN) - 275.1 pts
   3. Tyreek Hill (WR, MIA) - 262.7 pts
============================================================

🎯 YOUR TURN - Pick #5 (Round 1.5): Christian McCaffrey
🔍 Looking up: Christian McCaffrey
✅ Found: Christian McCaffrey (RB) - ID: player_12345
✅ YOUR PICK #5 (Round 1.5): Christian McCaffrey (RB)

⏳ Team 6 Pick #6 (Round 1.6): Tyreek Hill
📍 Pick #6 (Round 1.6, Team 6): Tyreek Hill (WR)
```

## Configuration

### Scoring Formats
- **ppr**: Point per reception (default)
- **half_ppr**: Half point per reception  
- **standard**: No reception points

### League Sizes
- Supports any league size (typically 8-14 teams)
- Snake draft order automatically adjusts

### API Configuration
The AI recommendation service endpoint is configured in the script:
```python
API_ENDPOINT = "YOUR API ENDPOINT URL"
```

## Data Storage

### Local Files
- `draft_session.json`: Current draft state (auto-saved after each pick)

### AWS DynamoDB
- Table: `2025-2026-fantasy-football-player-data`
- Contains player projections and historical stats
- Requires read permissions

## Troubleshooting

### Common Issues

**"No active draft session"**
- Run `python v2.py start` first to create a new draft

**"Failed to load player database"**
- Check AWS credentials and DynamoDB permissions
- Ensure internet connectivity

**"Could not find player"**
- Try alternate spellings or abbreviations
- Manually specify position when prompted
- Use defense command for DST: `def [team_name]`

**"API request failed"**
- Check internet connection
- Recommendation service may be temporarily unavailable
- You can still draft manually without recommendations

### Reset Everything
```bash
python v2.py reset
```

## Advanced Usage

### Manual Pick Entry
```bash
# Add a pick for another team
python v2.py add-pick --player "Josh Allen" --position QB --team 3

# Add your own pick outside interactive mode
python v2.py pick --player "Saquon Barkley" --position RB
```

### Viewing Draft State
```bash
# See recent picks and turn order
python v2.py board

# Check your roster composition
python v2.py status
```

## Contributing

This tool is designed for personal fantasy football drafts. Feel free to modify the roster limits, scoring settings, or add new features as needed for your league format.