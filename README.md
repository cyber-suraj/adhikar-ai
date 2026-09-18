# Adhikar AI

> Upload your rejection letter. We tell you what is wrong, which office to go to, and track it until it is fixed.

**Hackathon:** AWS First Commit — Bharat Builds Tour, Event 01
**Team:** NxtTech (P5R9HX)
**Track:** Ship It

---

## The Problem

Millions of Indians are rejected from welfare schemes (PM-KISAN, Ayushman Bharat, PMAY) due to fixable data mismatches. The citizen is never told *what* to fix or *where* to go. Most give up.

## The Solution

Adhikar AI is a post-rejection diagnostic and repair agent:

1. Upload your rejection letter (photo or PDF)
2. We extract the scheme, reason, and department using **AWS Textract**
3. We cross-reference your Aadhaar, land record, and bank passbook
4. We find the exact mismatch using fuzzy matching
5. **AWS Bedrock (Nova Lite)** explains it in Hindi / Marathi / English
6. We generate a pre-filled correction form for the right office
7. **AWS Step Functions** tracks your case: Diagnosed -> Filed -> In Review -> Resolved
8. **EventBridge + SNS** send you follow-up reminders

## Architecture

```
Browser (Amplify)
     |
API Gateway (REST)
     |
     +-- POST /presign   -> Lambda (presign)   -> S3 presigned URL
     +-- POST /analyze   -> Lambda (analyze)   -> Step Functions
     +-- GET  /status    -> Lambda (track)     -> DynamoDB
     
Step Functions Workflow:
  Extract (Textract) -> Match (fuzzywuzzy) -> Generate (Bedrock) -> Track (DynamoDB + SNS)
```

## AWS Services Used

| Service | Purpose |
|---------|---------|
| Amplify Hosting | Frontend deployment |
| Cognito | User authentication |
| API Gateway | REST API |
| Lambda | All compute (Python 3.12) |
| S3 | Document storage (encrypted) |
| Textract | OCR from rejection letters |
| Bedrock (Nova Lite) | Multilingual diagnosis + form generation |
| DynamoDB | Case records, status tracking |
| Step Functions | Workflow orchestration |
| EventBridge | Scheduled reminders |
| SNS | SMS/email notifications |
| CloudWatch | Logging and monitoring |
| SAM | Infrastructure as code |

## Local Setup

### Prerequisites
- AWS CLI configured (`aws configure`)
- AWS SAM CLI installed (`sam --version`)
- Node.js 18+ and npm
- Python 3.12

### Backend Deploy

```bash
cd backend
sam build
sam deploy --guided
# Stack name: adhikar-ai
# Region: us-east-1
```

### Frontend

```bash
cd frontend
cp .env.example .env.local
# Fill in your API Gateway URL from SAM outputs
npm install
npm run dev
```

## Demo Documents

The `samples/` folder contains simulated documents with deliberate mismatches:

- **Aadhaar:** Suraj **Khanase**, Father: Ramesh **Khanase**
- **Land Record (7/12):** Suraj **Kanase**, Father: Ramesh **Kanse**
- **Rejection Letter:** PM-KISAN rejected — details do not match

The name mismatch (Khanase vs Kanase) is what Adhikar AI detects and resolves.

## Team

- **Sumit Jagtap** — AWS deployment, architecture
- **Nandkishor Tamkhade** — Frontend, Bedrock integration
- **Suraj Khanase** — Textract, matching logic, demo, blog, submission
