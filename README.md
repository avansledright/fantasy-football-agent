# 🏈 Fantasy Football Draft Assistant (AI + AWS)

An **AI-powered draft assistant** built with:
- **Python 3.12** for the CLI + Lambda logic  
- **Amazon DynamoDB** for storing player stats  
- **Amazon Bedrock** (Claude 3.5 Haiku) for reasoning and recommendations  
- **Terraform** for infrastructure  

The agent helps you draft the **best available player** in real-time, considering:
- Your roster requirements (QB, RB, WR, TE, FLEX, DEF, K, Bench)  
- Players already drafted  
- Player performance stats from the NFLVerse dataset  

---

## 🚀 Features

- CLI for interacting with the draft assistant  
- AWS Lambda function powered by **Strands Agent SDK**  
- DynamoDB integration (stores player stats + metadata)  
- Bedrock LLM reasoning with tool-calling (`get_best_available_player`)  
- Real-time draft tracking (already drafted players + roster balance)  

---

## 📦 Setup

### 1. Clone repository
```bash
git clone https://github.com/your-org/fantasy-draft-assistant.git
cd fantasy-draft-assistant
```

### 2. Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure AWS
```bash
aws configure
```

Make sure your IAM user/role has access to:
- DynamoDB  
- Bedrock  
- Lambda  
- API Gateway  

### 4. Deploy infrastructure
```bash
cd infra
terraform init
terraform apply
```

This will provision:
- DynamoDB table  
- Lambda function  
- API Gateway endpoint  
- IAM roles & policies  

### 5. Populate DynamoDB with player stats
```bash
python scripts/populate-table.py
```

---

## 🖥 Usage

### CLI
```bash
python cli.py
```

Available commands:
- `draft next` → Suggest the best available player  
- `draft taken "Patrick Mahomes"` → Mark a player as drafted  
- `draft roster` → Show your current roster & bench  
- `draft reset` → Reset the draft state  

### Lambda (API Gateway)
You can also call the deployed agent directly:

```bash
curl -X POST https://<api-id>.execute-api.us-west-2.amazonaws.com/demo/agent \
  -H "Content-Type: application/json" \
  -d '{
    "team_needs": {"QB": 1, "RB": 2},
    "already_drafted": ["Patrick Mahomes", "Justin Jefferson"]
  }'
```

---

## 🛠 Development

- Code formatting: `black .`  
- Linting: `flake8 .`  
- Tests: `pytest`  

---

## 📚 References

- [NFLVerse Data](https://github.com/nflverse/nflverse-data)  
- [Amazon Bedrock](https://aws.amazon.com/bedrock/)  
- [Strands SDK](https://docs.strands.tools)  

---

## 📝 License
MIT License
