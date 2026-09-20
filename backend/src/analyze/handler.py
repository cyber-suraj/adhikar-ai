"""
Analyze Lambda - HTTP entry point that starts the Step Functions workflow
POST /analyze  { caseId, s3Key, lang? }
     -> starts execution, returns { executionArn, caseId }
"""
import json
import os
import uuid
import boto3
from datetime import datetime, timezone

sfn = boto3.client("stepfunctions")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]


def cors_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return cors_response(200, {})

    try:
        body = json.loads(event.get("body") or "{}")
        case_id = body.get("caseId") or str(uuid.uuid4())
        s3_key = body.get("s3Key") or body.get("key")
        lang = body.get("lang", "en")

        if not s3_key:
            return cors_response(400, {"error": "s3Key is required"})

        # Initial DynamoDB record - do not inject hardcoded demo applicant
        initial_item = {
            "caseId": case_id,
            "s3Key": s3_key,
            "lang": lang,
            "status": "Uploaded",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        # Only preserve scheme/applicantName if explicitly provided and not default demo
        if body.get("scheme") and body["scheme"] not in ("PM-KISAN", "default"):
            initial_item["scheme"] = body["scheme"]
        if body.get("applicantName") and body["applicantName"] not in ("Suraj Khanase", "Applicant", "default"):
            initial_item["applicantName"] = body["applicantName"]

        table.put_item(Item=initial_item)

        # Start Step Functions execution without injecting hardcoded values
        execution_input = {
            "caseId": case_id,
            "s3Key": s3_key,
            "lang": lang,
        }
        if "scheme" in initial_item:
            execution_input["scheme"] = initial_item["scheme"]
        if "applicantName" in initial_item:
            execution_input["applicantName"] = initial_item["applicantName"]

        execution = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"adhikar-{case_id[:8]}-{int(datetime.now().timestamp())}",
            input=json.dumps(execution_input),
        )
        return cors_response(200, {
            "caseId": case_id,
            "executionArn": execution["executionArn"],
            "status": "Uploaded",
            "message": "Analysis started. Poll /status/{caseId} for updates.",
        })
    except Exception as e:
        print(f"[analyze] error: {e}")
        return cors_response(500, {"error": str(e)})
