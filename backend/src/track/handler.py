"""
Step 6 - Status Tracking Lambda
GET  /status/{caseId}       -> full case record
PUT  /status/{caseId}       -> { status, notes? }  update status
Direct invoke (Step Functions): { caseId, status, action: "update" }
Status flow: Uploaded -> Extracted -> Matched -> Diagnosed -> Filed -> InReview -> Resolved
"""
import json
import os
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
sns = boto3.client("sns")
SNS_TOPIC = os.environ.get("SNS_TOPIC_ARN", "")

VALID_STATUSES = ["Uploaded", "Extracted", "Matched", "Diagnosed", "Filed", "InReview", "Resolved"]

STATUS_MESSAGES = {
    "en": {
        "Uploaded": "Your documents have been uploaded successfully.",
        "Extracted": "We have read your rejection letter.",
        "Matched": "We found the mismatch in your documents.",
        "Diagnosed": "Your case has been diagnosed. Please see the correction form.",
        "Filed": "Your correction request has been filed with the department.",
        "InReview": "Your case is under review by the department.",
        "Resolved": "Your correction has been approved! Re-apply for the scheme.",
    },
    "hi": {
        "Uploaded": "आपके दस्तावेज़ सफलतापूर्वक अपलोड हो गए।",
        "Extracted": "हमने आपका अस्वीकृति पत्र पढ़ लिया है।",
        "Matched": "हमें आपके दस्तावेज़ों में अंतर मिला।",
        "Diagnosed": "आपके मामले का निदान हो गया। सुधार फॉर्म देखें।",
        "Filed": "आपका सुधार अनुरोध विभाग में दाखिल कर दिया गया है।",
        "InReview": "आपका मामला विभाग द्वारा समीक्षाधीन है।",
        "Resolved": "आपका सुधार स्वीकृत हो गया! योजना के लिए फिर से आवेदन करें।",
    },
    "mr": {
        "Uploaded": "तुमचे कागदपत्र यशस्वीरित्या अपलोड केले गेले.",
        "Extracted": "आम्ही तुमचे नाकारण्याचे पत्र वाचले.",
        "Matched": "आम्हाला तुमच्या कागदपत्रांमध्ये फरक आढळला.",
        "Diagnosed": "तुमच्या प्रकरणाचे निदान झाले. सुधारणा फॉर्म पहा.",
        "Filed": "तुमची सुधारणा विनंती विभागाकडे दाखल केली गेली.",
        "InReview": "तुमचे प्रकरण विभागाकडून तपासणीत आहे.",
        "Resolved": "तुमची सुधारणा मंजूर झाली! योजनेसाठी पुन्हा अर्ज करा.",
    },
}


def cors_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,PUT,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def send_notification(case_id: str, new_status: str):
    if not SNS_TOPIC:
        return
    try:
        message = STATUS_MESSAGES["en"].get(new_status, f"Case {case_id} is now {new_status}")
        sns.publish(
            TopicArn=SNS_TOPIC,
            Message=message,
            Subject=f"Adhikar AI Update — {new_status}",
            MessageAttributes={
                "caseId": {"DataType": "String", "StringValue": case_id},
                "status": {"DataType": "String", "StringValue": new_status},
            },
        )
    except Exception as e:
        print(f"[track] SNS publish failed (non-fatal): {e}")


def lambda_handler(event, context):
    # ── Step Functions direct invocation ──────────────────────────
    if event.get("action") == "update":
        case_id = event["caseId"]
        new_status = event["status"]
        table.update_item(
            Key={"caseId": case_id},
            UpdateExpression="SET #s = :st, updatedAt = :ts",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":st": new_status,
                ":ts": datetime.now(timezone.utc).isoformat(),
            },
        )
        send_notification(case_id, new_status)
        return {"caseId": case_id, "status": new_status}

    # ── API Gateway invocation ────────────────────────────────────
    if event.get("httpMethod") == "OPTIONS":
        return cors_response(200, {})

    http_method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    case_id = path_params.get("caseId")

    if not case_id:
        return cors_response(400, {"error": "Missing caseId"})

    # ── GET /status/{caseId} ──────────────────────────────────────
    if http_method == "GET":
        try:
            response = table.get_item(Key={"caseId": case_id})
            item = response.get("Item")
            if not item:
                return cors_response(404, {"error": "Case not found", "caseId": case_id})

            # Build status history
            current_status = item.get("status", "Uploaded")
            messages = STATUS_MESSAGES
            return cors_response(200, {
                "caseId": case_id,
                "status": current_status,
                "scheme": item.get("scheme", "Unknown"),
                "rejectionReason": item.get("rejectionReason", "Unknown"),
                "mismatches": item.get("mismatches", []),
                "mismatchCount": item.get("mismatchCount", 0),
                "diagnosisEn": item.get("diagnosisEn", ""),
                "diagnosisHi": item.get("diagnosisHi", ""),
                "diagnosisMr": item.get("diagnosisMr", ""),
                "correctionForm": item.get("correctionForm", ""),
                "statusMessageEn": messages["en"].get(current_status, ""),
                "statusMessageHi": messages["hi"].get(current_status, ""),
                "statusMessageMr": messages["mr"].get(current_status, ""),
                "updatedAt": item.get("updatedAt", ""),
                "usedFallback": item.get("usedFallback", False),
            })
        except ClientError as e:
            return cors_response(500, {"error": str(e)})

    # ── PUT /status/{caseId} ──────────────────────────────────────
    if http_method == "PUT":
        try:
            body = json.loads(event.get("body") or "{}")
            new_status = body.get("status")
            notes = body.get("notes", "")

            if new_status not in VALID_STATUSES:
                return cors_response(400, {
                    "error": f"Invalid status. Must be one of: {VALID_STATUSES}"
                })

            table.update_item(
                Key={"caseId": case_id},
                UpdateExpression="SET #s = :st, updatedAt = :ts, notes = :n",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":st": new_status,
                    ":ts": datetime.now(timezone.utc).isoformat(),
                    ":n": notes,
                },
            )
            send_notification(case_id, new_status)
            return cors_response(200, {"caseId": case_id, "status": new_status, "updated": True})

        except ClientError as e:
            return cors_response(500, {"error": str(e)})

    return cors_response(405, {"error": "Method not allowed"})
