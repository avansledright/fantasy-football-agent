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
git clone https://github.com/avansledright/fantasy-draft-assistant.git
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
python scripts/stat_loader.py
python scripts/combine.py
EXPORT DYNAMODB_TABLE=<YOUR TABLE NAME>
EXPORT AWS_REGION=<AWS REGION>
python3 scripts/dynamodb_loader.py
```

---

## 🖥 Usage
You can use this in a variety of ways. Check out the "application" folder for an example CLI drafting application.

---

## 🛠 Development
### TO DO:
1. Create week-to-week team management
2. Add trading assistant
3. Combine all data loading scripts into one
---


## 📚 References

- [Fantasy Pros](https://www.fantasypros.com/)  
- [Amazon Bedrock](https://aws.amazon.com/bedrock/)  
- [Strands SDK](https://docs.strands.tools)  