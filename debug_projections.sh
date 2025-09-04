#!/bin/bash

# Debug script to see what's in your projections data
TEAM_ID=${1:-1}
WEEK=${2:-1}

echo "🔍 Debugging projections data for Week ${WEEK}..."
echo "=================================================="

# First, let's see the raw projections data
curl -s "https://14xsakutsl.execute-api.us-west-2.amazonaws.com/demo/coach?team_id=${TEAM_ID}&week=${WEEK}" | python3 -c '
import json, sys, re

try:
    data = json.load(sys.stdin)
    
    if "raw" in data:
        raw = data["raw"]
        print("📊 CHECKING FOR PROJECTIONS DATA IN RESPONSE...")
        print("=" * 60)
        
        # Look for mentions of specific players
        players_to_check = ["DK Metcalf", "Sam Darnold", "Cooper Kupp", "Josh Allen"]
        
        for player in players_to_check:
            if player in raw:
                # Find context around player mentions
                lines = raw.split("\n")
                for i, line in enumerate(lines):
                    if player in line:
                        print(f"\n🔍 {player} context:")
                        # Show 2 lines before and after for context
                        start = max(0, i-2)
                        end = min(len(lines), i+3)
                        for j in range(start, end):
                            marker = ">>> " if j == i else "    "
                            print(f"{marker}{lines[j]}")
                        break
        
        print("\n" + "=" * 60)
        print("📋 LOOKING FOR TEAM ROSTER DATA...")
        
        # Look for roster data
        if "CURRENT TEAM ROSTER:" in raw:
            roster_start = raw.find("CURRENT TEAM ROSTER:")
            roster_section = raw[roster_start:roster_start+1000]
            print(roster_section)
        
        print("\n" + "=" * 60)
        print("📈 LOOKING FOR PROJECTIONS DATA...")
        
        # Look for projections mentions
        if "projection" in raw.lower():
            proj_lines = [line for line in raw.split("\n") if "projection" in line.lower()]
            for line in proj_lines[:10]:  # Show first 10 projection mentions
                print(f"  {line.strip()}")
    
    else:
        print("No raw data found - response was already parsed JSON")
        print(json.dumps(data, indent=2)[:500])

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
'

echo ""
echo "🔧 SUGGESTION: Check your projections data source"
echo "   - Is it pulling 2024 season data instead of current?"
echo "   - Are player movements/trades updated?"