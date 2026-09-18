"""
Step 3 - Textract Extraction Lambda
Called by Step Functions with { caseId, s3Key }
Extracts: scheme name, rejection reason, department, applicant name
Stores result in DynamoDB
"""
import json
import os
import re
import boto3
from botocore.exceptions import ClientError

textract = boto3.client("textract", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
BUCKET = os.environ["BUCKET_NAME"]


# ── Patterns for PM-KISAN and common scheme keywords ──────────────
SCHEME_PATTERNS = [
    (r"PM[\s-]?KISAN", "PM-KISAN"),
    (r"PMAY|Pradhan\s*Mantri\s*Awas", "PMAY"),
    (r"Ayushman\s*Bharat|PMJAY|PM[\s-]?JAY", "Ayushman Bharat"),
    (r"PM[\s-]?Kaushal|PMKVY", "PMKVY"),
    (r"Atal\s*Pension|APY", "APY"),
    (r"PMSBY|Suraksha\s*Bima", "PMSBY"),
    (r"PMJJBY|Jeevan\s*Jyoti", "PMJJBY"),
    (r"Jan\s*Dhan|PMJDY", "Jan Dhan Yojana"),
    (r"MGNREGA|NREGA", "MGNREGA"),
    (r"state\s*pension|vridha\s*pension|old\s*age\s*pension", "Old Age Pension"),
]

REASON_PATTERNS = [
    (r"name\s*mismatch|name\s*does\s*not\s*match", "Name mismatch"),
    (r"date\s*of\s*birth\s*mismatch|DOB\s*mismatch|dob\s*does\s*not\s*match", "DOB mismatch"),
    (r"aadhaar\s*not\s*link|aadhaar\s*seeding", "Aadhaar not linked"),
    (r"bank\s*account\s*mismatch|account\s*number\s*mismatch", "Bank account mismatch"),
    (r"father.*mismatch|father.*does\s*not\s*match", "Father name mismatch"),
    (r"address\s*mismatch|address\s*does\s*not\s*match", "Address mismatch"),
    (r"land\s*record|survey\s*number", "Land record mismatch"),
    (r"details\s*do\s*not\s*match|details\s*mismatch", "Details mismatch"),
    (r"duplicate\s*application|already\s*registered", "Duplicate application"),
    (r"ineligible|not\s*eligible", "Ineligibility"),
]

DEPT_PATTERNS = [
    (r"agriculture|krishi", "Department of Agriculture"),
    (r"revenue|tehsildar|talathi", "Revenue Department"),
    (r"health|swasthya", "Department of Health"),
    (r"housing|awas", "Department of Housing"),
    (r"labour|mazdoor", "Department of Labour"),
    (r"social\s*welfare|samaj\s*kalyan", "Department of Social Welfare"),
    (r"pension", "Department of Social Welfare"),
]


def extract_text_from_s3(bucket: str, key: str) -> str:
    """Run Textract on an S3 object. Returns raw extracted text."""
    try:
        response = textract.detect_document_text(
            Document={"S3Object": {"Bucket": bucket, "Name": key}}
        )
        lines = [
            block["Text"]
            for block in response.get("Blocks", [])
            if block["BlockType"] == "LINE"
        ]
        return "\n".join(lines)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("InvalidParameterException", "UnsupportedDocumentException"):
            print(f"Textract cannot read document: {e}")
            return ""
        raise


def find_pattern(text: str, patterns: list) -> str:
    text_lower = text.lower()
    for pattern, label in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return label
    return "Unknown"


def extract_applicant_name(text: str) -> str:
    """Heuristic: find 'Name:' or 'Applicant:' followed by a value."""
    match = re.search(
        r"(?:applicant|name|naam)\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else "Unknown"


def lambda_handler(event, context):
    case_id = event.get("caseId")
    s3_key = event.get("s3Key") or event.get("key")

    if not case_id or not s3_key:
        raise ValueError(f"Missing caseId or s3Key in event: {event}")

    print(f"[extract] caseId={case_id} key={s3_key}")

    # ── OCR ──────────────────────────────────────────────────────
    raw_text = extract_text_from_s3(BUCKET, s3_key)

    if not raw_text:
        # Fallback: store minimal record and let user fill manually
        result = {
            "caseId": case_id,
            "rawText": "",
            "scheme": "Unknown",
            "rejectionReason": "Unknown",
            "department": "Unknown",
            "applicantName": "Unknown",
            "status": "NeedsManualInput",
            "extractFallback": True,
        }
    else:
        result = {
            "caseId": case_id,
            "rawText": raw_text[:2000],  # cap for DynamoDB
            "scheme": find_pattern(raw_text, SCHEME_PATTERNS),
            "rejectionReason": find_pattern(raw_text, REASON_PATTERNS),
            "department": find_pattern(raw_text, DEPT_PATTERNS),
            "applicantName": extract_applicant_name(raw_text),
            "status": "Extracted",
            "extractFallback": False,
        }

    # ── Store in DynamoDB ─────────────────────────────────────────
    table.put_item(Item=result)
    print(f"[extract] stored: scheme={result['scheme']} reason={result['rejectionReason']}")

    return result
