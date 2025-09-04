#!/bin/bash

# Usage: ./simple_lineup.sh [team_id] [week]
TEAM_ID=${1:-1}
WEEK=${2:-1}
URL="https://14xsakutsl.execute-api.us-west-2.amazonaws.com/demo/coach?team_id=${TEAM_ID}&week=${WEEK}"

echo "🏈 Fantasy Lineup for Team ${TEAM_ID}, Week ${WEEK}"
echo "=================================================="

curl -s "$URL" | python3 -c '
import json, sys, re, textwrap

try:
    data = json.load(sys.stdin)
    
    # Extract lineup data
    if "raw" in data:
        # Find JSON in the raw text
        raw = data["raw"]
        match = re.search(r"```json\s*({.*?})\s*```", raw, re.DOTALL)
        if not match:
            # Alternative: look for any JSON with lineup
            match = re.search(r"({.*?\"lineup\".*?})", raw, re.DOTALL | re.MULTILINE)
        
        if match:
            lineup_data = json.loads(match.group(1))
        else:
            print("❌ No JSON found")
            print(raw[:300])
            sys.exit()
    else:
        lineup_data = data
    
    # Display lineup
    if "lineup" in lineup_data:
        print("\n🏆 STARTING LINEUP:")
        total = 0
        for p in lineup_data["lineup"]:
            slot = p.get("slot", "?")
            player = p.get("player", "Empty")
            projected = p.get("projected", 0)
            adjusted = p.get("adjusted", projected)
            team = p.get("team", "")
            
            if player and player != "Empty":
                total += adjusted
                team_part = f" ({team})" if team else ""
                print(f"  {slot:>4}: {player:<22}{team_part:<6} {projected:>4.1f} pts")
        
        print(f"\n  💯 TOTAL PROJECTED: {total:.1f} points")
        
        # Show bench
        if "bench" in lineup_data and lineup_data["bench"]:
            print(f"\n📋 BENCH (Top 5):")
            for p in lineup_data["bench"][:5]:
                name = p.get("name", p.get("player", "?"))
                pos = p.get("position", "?")
                proj = p.get("projected", 0)
                print(f"  {pos:>4}: {name:<22} {proj:>4.1f} pts")
        
        # Show explanations/reasoning
        if "explanations" in lineup_data and lineup_data["explanations"]:
            print(f"\n💡 COACH ANALYSIS:")
            print("=" * 50)
            explanation = lineup_data["explanations"]
            # Clean up the explanation text
            explanation = explanation.replace("Key changes made:", "\n🔄 Key changes made:")
            explanation = explanation.replace("1)", "\n  1)")
            explanation = explanation.replace("2)", "\n  2)")
            explanation = explanation.replace("3)", "\n  3)")
            explanation = explanation.replace("4)", "\n  4)")
            explanation = explanation.replace("5)", "\n  5)")
            
            # Word wrap at 60 characters
            wrapped = textwrap.fill(explanation, width=60, subsequent_indent="  ")
            print(wrapped)
            print("")
        
        # Also extract reasoning from raw text if available
        elif "raw" in data:
            # Look for analysis in the raw response before the JSON
            raw_text = data["raw"]
            
            # Extract text before the JSON block
            json_start = raw_text.find("```json")
            if json_start > 0:
                analysis_text = raw_text[:json_start].strip()
                
                # Look for analysis sections
                analysis_sections = []
                if "## Lineup Analysis:" in analysis_text:
                    sections = analysis_text.split("##")
                    for section in sections:
                        if section.strip() and ("Analysis" in section or "Key" in section or "Final" in section):
                            analysis_sections.append(section.strip())
                
                if analysis_sections:
                    print(f"\n💡 COACH ANALYSIS:")
                    print("=" * 50)
                    for section in analysis_sections:
                        # Clean up formatting
                        clean_section = re.sub(r"\*\*(.*?)\*\*", r"\1", section)  # Remove **bold**
                        clean_section = clean_section.replace("- ", "  • ")
                        
                        wrapped = textwrap.fill(clean_section, width=60)
                        print(wrapped)
                        print("")
    else:
        print("❌ No lineup found")
        print(json.dumps(lineup_data, indent=2)[:200])

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
'

echo "=================================================="