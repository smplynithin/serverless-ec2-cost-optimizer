# 🤖 Serverless EC2 Cost Optimizer
### Automated EC2 Stop/Start System with Override Protection, TTL Auto-Expiry, Audit Logging & Email Alerts

![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20EC2%20%7C%20DynamoDB%20%7C%20S3%20%7C%20SNS%20%7C%20EventBridge-orange?style=flat-square&logo=amazonaws)
![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=flat-square)

---

## 📌 What This Project Does

This system **automatically stops all dev EC2 instances every night at 11 PM IST** and **starts them back every morning at 8 AM IST** — saving AWS costs with zero manual effort.

But it's not just a simple on/off switch. It's a **production-grade lifecycle manager** with:

- 🛡️ **Developer Override Protection** — any developer can protect their instance from being stopped (e.g. "I'm deploying tonight")
- ⏱️ **TTL Auto-Expiry** — override records automatically expire at 8 AM next day via DynamoDB TTL. No more forgotten overrides accidentally protecting instances forever.
- 📧 **Email Reports** — every run sends a detailed email showing what was stopped, what was skipped, and why
- 📁 **Audit Logs** — every run saves a JSON log to S3 for full traceability
- 🏷️ **Tag-Based Discovery** — automatically finds instances by tags, no hardcoded IDs
- ☁️ **100% Serverless** — no servers to manage, runs only when needed

---

## 💰 Cost Savings Example

| Scenario | Monthly Saving |
|---|---|
| 1 x t3.micro stopped 10hrs/night | ~$3/month |
| 5 x t3.micro stopped 10hrs/night | ~$15/month |
| 10 x t3.micro stopped 10hrs/night | ~$30/month |
| 10 x t3.large stopped 10hrs/night | ~$120/month |

> Savings = (hourly rate × 10 hrs/night × 30 days × number of instances)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   EventBridge          Lambda              AWS Services     │
│   ──────────           ──────              ────────────     │
│                                                             │
│   11 PM IST  ───────→  ec2-lifecycle  ───→  EC2 (stop)      │
│   {"action":            -manager      ───→  DynamoDB        │
│    "stop"}                   │              (check override) │
│                              │         ───→  S3              │
│   8 AM IST   ───────→        │              (save audit log) │
│   {"action":                 │         ───→  SNS             │
│    "start"}                  │              (send email)     │
│                              ↓                              │
│                         CloudWatch                          │
│                         (debug logs)                        │
└─────────────────────────────────────────────────────────────┘
```

### Flow — What happens every night at 11 PM IST:

```
EventBridge fires
      ↓
Lambda searches EC2 for instances tagged Env=dev, AutoStop=true
      ↓
For each instance → check DynamoDB for override
      ↓                              ↓
  No override?               Override = true?
      ↓                              ↓
  Stop instance              Skip instance
      ↓                              ↓
      └──────────────┬───────────────┘
                     ↓
             Save JSON log → S3
                     ↓
             Send email report → SNS → Your inbox

Next morning 8 AM IST:
DynamoDB TTL auto-deletes expired override records ✅
EventBridge fires → Lambda starts all tagged instances
```

---

## ☁️ AWS Services Used

| Service | Purpose | Why This Service |
|---|---|---|
| **Lambda** | Core logic — finds, stops, skips instances | Serverless, no server to manage, pay per run |
| **EventBridge** | Cron scheduler — triggers Lambda at exact times | Native AWS scheduler, reliable, cron syntax |
| **EC2** | The servers being managed | Target of the automation |
| **DynamoDB** | Override protection database with TTL | Key-value lookup, millisecond response, native TTL support |
| **S3** | Audit log storage | Cheap, durable, infinite retention |
| **SNS** | Email notifications | Managed pub/sub, supports email protocol |
| **IAM** | Least-privilege security role | Security best practice — only needed permissions |
| **CloudWatch** | Lambda execution logs | Native Lambda logging, free tier included |

---

## 📂 Project Structure

```
serverless-ec2-cost-optimizer/
│
├── lambda_function.py                     # Main Lambda code
│
├── iam/
│   └── lambda-ec2-lifecycle-policy.json   # IAM inline policy
│
├── dynamodb/
│   └── override-item-example.json         # DynamoDB override record with TTL
│
├── eventbridge/
│   ├── nightly-stop-rule.json             # EventBridge cron rule (stop)
│   └── morning-start-rule.json            # EventBridge cron rule (start)
│
├── tests/
│   ├── test-stop-event.json               # Lambda test event (stop)
│   └── test-start-event.json              # Lambda test event (start)
│
└── README.md
```

---

## 🚀 Setup Guide (Step by Step)

### Prerequisites
- AWS Account
- IAM user with admin access
- EC2 instance running in your target region

---

### Step 1 — Tag your EC2 instance

Go to **EC2 → Instances → Tags → Manage tags** and add:

| Key | Value |
|---|---|
| `Env` | `dev` |
| `AutoStop` | `true` |

> ⚠️ Values are case-sensitive. Use lowercase `true`, not `True`.

---

### Step 2 — Create DynamoDB table

```
Table name:     ec2-override
Partition key:  instance_id (String)
```

**Enable TTL on the table:**
1. Go to the table → **Additional settings** tab
2. Find **Time to Live (TTL)** → click **Enable**
3. TTL attribute name: `expires_at`
4. Click **Enable TTL**

> This means any override record with an `expires_at` timestamp in the past will be **automatically deleted by DynamoDB** — no manual cleanup needed.

---

### Step 3 — Create S3 bucket

```
Bucket name:          ec2-lifecycle-logs-<yourname>
Region:               us-east-1
Block public access:  ON
```

---

### Step 4 — Create IAM Role

```
Role name:      lambda-ec2-lifecycle-role
Trusted entity: Lambda
Policy:         lambda-ec2-lifecycle-policy (inline)
```

See full policy JSON in `iam/lambda-ec2-lifecycle-policy.json`

---

### Step 5 — Create SNS Topic

```
Topic name:   ec2-stop-alert
Type:         Standard
Protocol:     Email
Endpoint:     your-email@gmail.com
```

> ⚠️ Confirm the subscription email before proceeding.

---

### Step 6 — Deploy Lambda Function

```
Function name:    ec2-lifecycle-manager
Runtime:          Python 3.12
Execution role:   lambda-ec2-lifecycle-role
Timeout:          1 minute
```

Update these 2 lines in `lambda_function.py`:
```python
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:ec2-stop-alert'
S3_BUCKET     = 'ec2-lifecycle-logs-yourname'
```

---

### Step 7 — Create EventBridge Rules

| Rule | Cron | Payload |
|---|---|---|
| `nightly-ec2-stop` | `cron(30 17 * * ? *)` | `{"action": "stop"}` |
| `morning-ec2-start` | `cron(30 2 * * ? *)` | `{"action": "start"}` |

> IST = UTC + 5:30 → 11 PM IST = 17:30 UTC → `cron(30 17 * * ? *)`

---

## ⏱️ TTL — Override Auto-Expiry

### The Problem Without TTL:
A developer adds an override record saying *"don't stop my instance tonight"* — but forgets to remove it. The instance never gets stopped again. AWS bill grows silently.

### The Solution — DynamoDB TTL:
Every override record has an `expires_at` field — a Unix timestamp. When that time passes, DynamoDB **automatically deletes the record.** No Lambda, no cron job, no manual work.

### Override Lifecycle:
```
9 PM  — Developer adds override with expires_at = tomorrow 8 AM
11 PM — Lambda checks DynamoDB → override exists → instance SKIPPED ✅
8 AM  — DynamoDB TTL auto-deletes the record ✅
11 PM — Lambda checks DynamoDB → no override → instance STOPPED ✅
```

### How to calculate expires_at (Unix timestamp):

```python
from datetime import datetime
import pytz

ist = pytz.timezone('Asia/Kolkata')
# Set expiry to tomorrow 8 AM IST
expiry = datetime(2026, 4, 14, 8, 0, 0, tzinfo=ist)
print(int(expiry.timestamp()))
# Output: 1744956600
```

Or use [epochconverter.com](https://epochconverter.com) → pick tomorrow 8 AM IST → copy the Unix timestamp.

---

## 🧪 Testing

### Test 1 — Normal Stop (no override)

Go to **Lambda → Test** and use this event:
```json
{ "action": "stop" }
```

Expected result:
```json
{
  "statusCode": 200,
  "processed": 1,
  "skipped": 0
}
```

---

### Test 2 — Override Active (instance protected)

Add a record to DynamoDB `ec2-override` table (see `dynamodb/override-item-example.json`), then run the same test.

Expected result:
```json
{
  "statusCode": 200,
  "processed": 0,
  "skipped": 1
}
```

Email should show:
```
Skipped — override active (1):
  - Nithin (i-0faa1eb99978490e8) SKIPPED — deploying tonight
```

---

## 📧 Sample Email Report

```
EC2 Nightly Report
==================
Time: 2026-04-11 23:00 IST

Stopped (1):
  - Nithin (i-0faa1eb99978490e8) STOPPED

Skipped — override active (0):
  None

Audit log: s3://ec2-lifecycle-logs-nithin
```

---

## 📁 Sample Audit Log (S3)

File: `logs/2026-04-11_17-30.json`

```json
{
  "timestamp": "2026-04-11T17:30:00.123456",
  "action": "stop",
  "stopped_or_started": [
    {
      "id": "i-0faa1eb99978490e8",
      "name": "Nithin"
    }
  ],
  "skipped": []
}
```

---

## 🔐 IAM Policy — Principle of Least Privilege

This project follows AWS security best practices. Lambda is granted **only** the permissions it needs:

```
ec2:StopInstances      → to stop tagged instances
ec2:StartInstances     → to start tagged instances
ec2:DescribeInstances  → to find instances by tags
dynamodb:GetItem       → to check override records
dynamodb:PutItem       → future: allow Lambda to set overrides
dynamodb:DeleteItem    → future: allow Lambda to clear overrides
sns:Publish            → to send email reports
s3:PutObject           → to save audit logs
logs:*                 → to write CloudWatch debug logs
```

---

## 💡 Key DevOps Concepts Demonstrated

- **Infrastructure as Code mindset** — tag-based discovery instead of hardcoded IDs
- **Principle of Least Privilege** — IAM role with exact permissions only
- **Event-driven architecture** — EventBridge → Lambda → multiple services
- **TTL-based auto-expiry** — DynamoDB native TTL prevents forgotten overrides
- **Audit trail** — every action logged to S3 for compliance
- **Graceful handling** — override system prevents accidental disruptions
- **Serverless** — zero idle cost, scales automatically

---

## 🧠 Interview Talking Points

> *"I built a serverless EC2 cost optimizer on AWS. It uses EventBridge to trigger a Lambda function on a cron schedule. Lambda discovers instances dynamically using tag-based filtering instead of hardcoded IDs. Before stopping any instance, it checks a DynamoDB table for developer overrides — if a developer is deploying, they add a record and Lambda skips that instance. I also added DynamoDB TTL so override records auto-expire at 8 AM next day — this prevents the real-world problem of forgotten overrides keeping instances running forever. Every run saves a JSON audit log to S3 and sends a detailed email report via SNS. The IAM role follows least-privilege — Lambda has only the exact permissions it needs."*

---

## 👨‍💻 Author

**Nithin** — Durability CAE Engineer transitioning to DevOps
📍 Bangalore, India
🔗 [GitHub](https://github.com/yourusername)

---

## 📄 License

MIT License — feel free to use and modify.
