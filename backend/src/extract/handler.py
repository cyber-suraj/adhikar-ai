"""
Step 3 - Textract Extraction Lambda
Called by Step Functions with { caseId, s3Key, s3Bucket? }
Extracts: scheme name, rejection reason, department, applicant name, father name, dob, address, aadhaar_last4
Stores result in DynamoDB
"""
import json
import os
import re
import boto3
from botocore.exceptions import ClientError

textract = boto3.client("textract", region_name="us-east-1")
s3_client = boto3.client("s3", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
DEFAULT_BUCKET = os.environ.get("BUCKET_NAME", "")

# ── Patterns for PM-KISAN and common scheme keywords ──────────────
SCHEME_PATTERNS = [
    (r"PM[\s-]?KISAN|Kisan\s*Samman", "PM-KISAN"),
    (r"PMAY|Pradhan\s*Mantri\s*Awas|Awas\s*Yojana", "PMAY"),
    (r"Ayushman\s*Bharat|PMJAY|PM[\s-]?JAY|Jan\s*Arogya", "Ayushman Bharat"),
    (r"PM[\s-]?Kaushal|PMKVY|Skill\s*India", "PMKVY"),
    (r"Atal\s*Pension|APY", "APY"),
    (r"PMSBY|Suraksha\s*Bima", "PMSBY"),
    (r"PMJJBY|Jeevan\s*Jyoti", "PMJJBY"),
    (r"Jan\s*Dhan|PMJDY", "Jan Dhan Yojana"),
    (r"MGNREGA|NREGA|Rozgar", "MGNREGA"),
    (r"state\s*pension|vridha\s*pension|old\s*age\s*pension", "Old Age Pension"),
    (r"certificate|training|session|participation|workshop", "Skill Training & Certification"),
]

REASON_PATTERNS = [
    (r"name\s*mismatch|name\s*does\s*not\s*match", "Name mismatch"),
    (r"date\s*of\s*birth\s*mismatch|DOB\s*mismatch|dob\s*does\s*not\s*match", "DOB mismatch"),
    (r"aadhaar\s*not\s*link|aadhaar\s*seeding|uid\s*not\s*link", "Aadhaar not linked"),
    (r"bank\s*account\s*mismatch|account\s*number\s*mismatch|ifsc\s*mismatch", "Bank account mismatch"),
    (r"father.*mismatch|father.*does\s*not\s*match", "Father name mismatch"),
    (r"address\s*mismatch|address\s*does\s*not\s*match", "Address mismatch"),
    (r"land\s*record|survey\s*number|khatiyan|7\/12", "Land record mismatch"),
    (r"details\s*do\s*not\s*match|details\s*mismatch|record\s*mismatch", "Details mismatch"),
    (r"duplicate\s*application|already\s*registered", "Duplicate application"),
    (r"ineligible|not\s*eligible", "Ineligibility"),
]

DEPT_PATTERNS = [
    (r"agriculture|krishi", "Department of Agriculture"),
    (r"revenue|tehsildar|talathi", "Revenue Department"),
    (r"health|swasthya", "Department of Health"),
    (r"housing|awas", "Department of Housing"),
    (r"labour|mazdoor|shram", "Department of Labour"),
    (r"social\s*welfare|samaj\s*kalyan", "Department of Social Welfare"),
    (r"education|shiksha|tech\s*talks?|training", "Department of Education & Training"),
]

DEMO_FALLBACK_DATA = {
    "applicantName": "Suraj Khanase",
    "fatherName": "Ramesh Khanase",
    "dob": "12/05/1998",
    "address": "Wagholi, Haveli, Pune, Maharashtra",
    "aadhaarLast4": "1234",
    "scheme": "PM-KISAN",
    "rejectionReason": "Name mismatch",
    "department": "Department of Agriculture",
}


def extract_text_from_s3(bucket: str, key: str) -> str:
    """Run Textract on an S3 object or read .txt directly. Returns raw extracted text."""
    if not key:
        return ""

    if key.lower().endswith(".txt"):
        try:
            resp = s3_client.get_object(Bucket=bucket, Key=key)
            content = resp["Body"].read().decode("utf-8", errors="ignore")
            print(f"[extract] Read {len(content)} chars directly from .txt in S3")
            return content
        except Exception as e:
            print(f"[extract] Failed reading .txt directly from S3: {e}")

    # For images and PDFs, call Textract detect_document_text
    response = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    lines = [
        block["Text"]
        for block in response.get("Blocks", [])
        if block["BlockType"] == "LINE"
    ]
    extracted = "\n".join(lines)
    print(f"[extract] Textract extracted {len(lines)} lines from s3://{bucket}/{key}")
    return extracted


def find_pattern(text: str, patterns: list) -> str:
    text_lower = text.lower()
    for pattern, label in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return label
    return "Unknown"


def extract_applicant_name(lines: list, full_text: str) -> str:
    """Extract applicant or recipient name from document lines or text."""
    # 1. Regex pattern on full text for explicit Applicant/Name labels
    m = re.search(
        r"(?:applicant(?:\s+name)?|name|naam|citizen(?:\s+name)?)\s*[:\-]\s*([A-Za-z]+(?:\s+[A-Za-z]+){1,3})",
        full_text,
        re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).strip()
        if not re.search(r"^(?:pune|maharashtra|kharif|rabi|village|taluka|district|helpdesk|office)$", candidate, re.I):
            return candidate

    # 2. 'To,' pattern (rejection letters)
    m = re.search(r"to\s*,\s*\n\s*([A-Za-z]+(?:\s+[A-Za-z]+){1,3})", full_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 3. 'Presented to' / 'Awarded to' pattern (certificates)
    for i, line in enumerate(lines):
        clean = line.strip()
        if re.search(r"(?:presented\s+to|awarded\s+to|certify\s+that|certificate\s+of)\b", clean, re.IGNORECASE):
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j].strip()
                words = candidate.split()
                if 2 <= len(words) <= 4 and all(w.isalpha() for w in words):
                    if not re.search(r"\b(?:for|actively|participating|live|session|held|september|date|training)\b", candidate, re.IGNORECASE):
                        return candidate

    # 4. Search lines for 2-3 word capitalized person names
    for line in lines:
        words = line.strip().split()
        if 2 <= len(words) <= 3 and all(w.isalpha() and w[0].isupper() for w in words):
            if not re.search(r"\b(?:Government|Maharashtra|Department|Agriculture|District|Helpdesk|Pune|Certificate|Participation)\b", line, re.IGNORECASE):
                return line.strip()

    return "Unknown"


def extract_father_name(lines: list, full_text: str, applicant_name: str) -> str:
    m = re.search(
        r"(?:father(?:'s)?(?:\s+name)?|s/o|d/o|w/o|shri|pita(?:\s+ka\s+naam)?)\s*[:\-]\s*([A-Za-z]+(?:\s+[A-Za-z]+){1,3})",
        full_text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    # If applicant name has 3 words (First Middle Last), the middle name is often the father's name
    if applicant_name and applicant_name != "Unknown":
        parts = applicant_name.split()
        if len(parts) == 3:
            return f"{parts[1]} {parts[2]}"
    return "Unknown"


def extract_dob(full_text: str) -> str:
    m = re.search(r"(?:dob|date\s*of\s*birth|janm\s*tithi)\s*[:\-]\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", full_text, re.IGNORECASE)
    return m.group(1).strip() if m else "Unknown"


def extract_address(full_text: str) -> str:
    m = re.search(r"(?:village|taluka|district|address|dist)\s*[:\-]\s*([^\n\r]+)", full_text, re.IGNORECASE)
    return m.group(1).strip() if m else "Unknown"


def extract_aadhaar_last4(full_text: str) -> str:
    m = re.search(r"(?:aadhaar|uidai|uid).*?(\d{4})(?!\d)", full_text, re.IGNORECASE)
    return m.group(1).strip() if m else "Unknown"


def lambda_handler(event, context):
    case_id = event.get("caseId")
    s3_key = event.get("s3Key") or event.get("key")
    s3_bucket = event.get("s3Bucket") or DEFAULT_BUCKET

    if not case_id or not s3_key:
        raise ValueError(f"Missing caseId or s3Key in event: {event}")

    print(f"[extract] caseId={case_id} bucket={s3_bucket} key={s3_key}")

    used_fallback = False
    textract_failed = False
    raw_text = ""
    lines = []

    is_demo = "demo" in str(case_id).lower()

    if not is_demo:
        try:
            raw_text = extract_text_from_s3(s3_bucket, s3_key)
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if not raw_text:
                print(f"[WARNING] No text returned from Textract for s3://{s3_bucket}/{s3_key}")
                textract_failed = True
        except Exception as e:
            print(f"[WARNING] Textract extraction failed with exception: {e}")
            textract_failed = True
            used_fallback = True

    if is_demo:
        print(f"[extract] Demo case detected ({case_id}), using demo reference data")
        applicant_name = DEMO_FALLBACK_DATA["applicantName"]
        father_name = DEMO_FALLBACK_DATA["fatherName"]
        dob = DEMO_FALLBACK_DATA["dob"]
        address = DEMO_FALLBACK_DATA["address"]
        aadhaar_last4 = DEMO_FALLBACK_DATA["aadhaarLast4"]
        scheme = DEMO_FALLBACK_DATA["scheme"]
        reason = DEMO_FALLBACK_DATA["rejectionReason"]
        department = DEMO_FALLBACK_DATA["department"]
    elif textract_failed:
        print(f"[WARNING] Textract failed for caseId={case_id}. Returning null fields with textract_failed=True")
        used_fallback = True
        applicant_name = None
        father_name = None
        dob = None
        address = None
        aadhaar_last4 = None
        scheme = event.get("scheme")
        reason = "Extraction failed"
        department = None
    else:
        applicant_name = extract_applicant_name(lines, raw_text)
        father_name = extract_father_name(lines, raw_text, applicant_name)
        dob = extract_dob(raw_text)
        address = extract_address(raw_text)
        aadhaar_last4 = extract_aadhaar_last4(raw_text)

        scheme = find_pattern(raw_text, SCHEME_PATTERNS)
        if scheme == "Unknown":
            scheme = event.get("scheme") or "Government Welfare Scheme"

        reason = find_pattern(raw_text, REASON_PATTERNS)
        if reason == "Unknown":
            reason = "Details mismatch"

        department = find_pattern(raw_text, DEPT_PATTERNS)
        if department == "Unknown":
            department = "Concerned Government Department"

    result = {
        "caseId": case_id,
        "s3Bucket": s3_bucket,
        "s3Key": s3_key,
        "rawText": raw_text[:2000] if raw_text else "",
        "extractedFields": {
            "name": applicant_name,
            "father_name": father_name,
            "dob": dob,
            "address": address,
            "aadhaar_last4": aadhaar_last4,
        },
        "applicantName": applicant_name,
        "fatherName": father_name,
        "dob": dob,
        "address": address,
        "aadhaarLast4": aadhaar_last4,
        "scheme": scheme,
        "rejectionReason": reason,
        "department": department,
        "status": "Extracted",
        "extractFallback": used_fallback,
        "textract_failed": textract_failed,
    }

    # Store in DynamoDB
    table.put_item(Item=result)
    print(f"[extract] stored: applicant={applicant_name} scheme={scheme} reason={reason} fallback={used_fallback} textract_failed={textract_failed}")

    return result
