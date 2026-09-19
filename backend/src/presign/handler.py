"""
Step 2 - Presigned URL Lambda
POST /presign  -> { uploadUrl, key, caseId }
"""
import json
import os
import uuid
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]


def cors_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST,GET,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return cors_response(200, {})

    try:
        body = json.loads(event.get("body") or "{}")
        file_type = body.get("fileType", "image/jpeg")
        doc_type = body.get("docType", "rejection_letter")  # rejection_letter | aadhaar | land_record | bank_passbook

        case_id = body.get("caseId") or str(uuid.uuid4())
        # Determine extension
        ext_map = {
            "image/jpeg": "jpg", "image/jpg": "jpg",
            "image/png": "png", "application/pdf": "pdf",
            "text/plain": "txt"
        }
        ext = ext_map.get(file_type, "jpg")
        key = f"cases/{case_id}/{doc_type}.{ext}"

        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET, "Key": key, "ContentType": file_type},
            ExpiresIn=300,
        )
        return cors_response(200, {"uploadUrl": url, "key": key, "caseId": case_id})

    except ClientError as e:
        print(f"S3 error: {e}")
        return cors_response(500, {"error": "Could not generate upload URL", "detail": str(e)})
    except Exception as e:
        print(f"Unexpected error: {e}")
        return cors_response(500, {"error": "Internal error", "detail": str(e)})
