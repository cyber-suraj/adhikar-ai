"""
Step 4 - Fuzzy Matching Lambda
Called by Step Functions with the extract result.
Compares simulated documents (Aadhaar vs land record vs bank) and
detects field-level mismatches using fuzzywuzzy.
In production: fetch from DigiLocker API. For hackathon: use stored
user profile documents in DynamoDB.
"""
import json
import os
import boto3
from decimal import Decimal
from fuzzywuzzy import fuzz

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

MATCH_THRESHOLD = 85  # below this score = mismatch


# ── Simulated document store (replaces DigiLocker for hackathon) ──
DEMO_DOCUMENTS = {
    "aadhaar": {
        "name": "Suraj Khanase",
        "dob": "12/05/1998",
        "fatherName": "Ramesh Khanase",
        "address": "Pune, Maharashtra",
        "aadhaarNumber": "XXXX-XXXX-1234",
    },
    "land_record": {
        "name": "Suraj Kanase",
        "fatherName": "Ramesh Kanse",
        "surveyNumber": "124/2",
        "area": "0.8 hectares",
        "district": "Pune",
    },
    "bank_passbook": {
        "name": "Suraj Khanase",
        "accountNumber": "XXXX1234",
        "ifsc": "SBIN0001234",
        "bankName": "State Bank of India",
    },
}

FIELD_LABELS = {
    "name": "Applicant Name",
    "fatherName": "Father's Name",
    "dob": "Date of Birth",
    "address": "Address",
}

CORRECTION_OFFICES = {
    "name": {
        "office": "Tehsildar Office",
        "process": "Submit Form 6 with original Aadhaar and land record",
        "timeline": "7-15 working days",
    },
    "fatherName": {
        "office": "Tehsildar Office",
        "process": "Submit affidavit + Form 6 with both documents",
        "timeline": "7-15 working days",
    },
    "dob": {
        "office": "Aadhaar Enrollment Center",
        "process": "Submit birth certificate or school leaving certificate",
        "timeline": "3-7 working days",
    },
    "address": {
        "office": "Gram Panchayat / Municipal Office",
        "process": "Submit current utility bill and residency proof",
        "timeline": "5-10 working days",
    },
}


def compare_field(val_a: str, val_b: str) -> int:
    """Return similarity score 0-100."""
    if not val_a or not val_b:
        return 0
    return fuzz.token_sort_ratio(val_a.lower().strip(), val_b.lower().strip())


def detect_mismatches(doc_a: dict, doc_b: dict, source_a: str, source_b: str) -> list:
    """Compare two documents field by field. Return list of mismatch dicts."""
    mismatches = []
    common_fields = set(doc_a.keys()) & set(doc_b.keys()) & set(FIELD_LABELS.keys())

    for field in common_fields:
        val_a = doc_a.get(field, "")
        val_b = doc_b.get(field, "")
        score = compare_field(val_a, val_b)
        if score < MATCH_THRESHOLD:
            correction = CORRECTION_OFFICES.get(field, {
                "office": "Concerned Government Office",
                "process": "Contact the issuing authority",
                "timeline": "7-14 working days",
            })
            mismatches.append({
                "field": field,
                "fieldLabel": FIELD_LABELS[field],
                "valueA": val_a,
                "sourceA": source_a,
                "valueB": val_b,
                "sourceB": source_b,
                "similarityScore": score,
                "correctionOffice": correction["office"],
                "correctionProcess": correction["process"],
                "estimatedTimeline": correction["timeline"],
            })
    return mismatches


def lambda_handler(event, context):
    # Accept both direct call and Step Functions envelope
    case_id = event.get("caseId")
    extract_result = event.get("extractResult", event)
    applicant_name_from_letter = extract_result.get("applicantName", "Unknown")

    print(f"[match] caseId={case_id}")

    # ── Get documents (demo uses hardcoded; production: DynamoDB lookup) ──
    aadhaar = DEMO_DOCUMENTS["aadhaar"]
    land = DEMO_DOCUMENTS["land_record"]
    bank = DEMO_DOCUMENTS["bank_passbook"]

    mismatches = []
    mismatches.extend(detect_mismatches(aadhaar, land, "Aadhaar", "Land Record (7/12)"))
    mismatches.extend(detect_mismatches(aadhaar, bank, "Aadhaar", "Bank Passbook"))

    # Also check applicant name from rejection letter vs Aadhaar
    if applicant_name_from_letter != "Unknown":
        letter_doc = {"name": applicant_name_from_letter}
        aadhaar_name_only = {"name": aadhaar["name"]}
        mismatches.extend(detect_mismatches(letter_doc, aadhaar_name_only, "Rejection Letter", "Aadhaar"))

    # Deduplicate by field
    seen = set()
    unique_mismatches = []
    for m in mismatches:
        if m["field"] not in seen:
            seen.add(m["field"])
            unique_mismatches.append(m)

    result = {
        "caseId": case_id,
        "mismatches": unique_mismatches,
        "mismatchCount": len(unique_mismatches),
        "aadhaarName": aadhaar["name"],
        "landName": land["name"],
        "status": "Matched",
    }

    # ── Update DynamoDB ────────────────────────────────────────────
    table.update_item(
        Key={"caseId": case_id},
        UpdateExpression="SET mismatches = :m, mismatchCount = :c, #s = :st",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":m": unique_mismatches,
            ":c": len(unique_mismatches),
            ":st": "Matched",
        },
    )

    print(f"[match] found {len(unique_mismatches)} mismatches")
    return result
