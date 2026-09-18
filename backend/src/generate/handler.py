"""
Step 5 - Bedrock Generation Lambda
Generates:
  1. Plain-language diagnosis in Hindi / Marathi / English
  2. Pre-filled correction form (text template)
Falls back to template-based generation if Bedrock unavailable.
"""
import json
import os
import boto3
from botocore.exceptions import ClientError

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

MODEL_ID = "amazon.nova-lite-v1:0"

LANG_NAMES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "en": "English",
}

# ── Fallback templates (used when Bedrock unavailable) ────────────
FALLBACK_DIAGNOSIS = {
    "en": (
        "Your application was rejected because of a data mismatch. "
        "The name on your {sourceA} ({valueA}) does not match the name on your {sourceB} ({valueB}). "
        "You need to visit the {correctionOffice} to correct this. "
        "The process: {correctionProcess}. Expected time: {estimatedTimeline}."
    ),
    "hi": (
        "आपका आवेदन डेटा मेल न खाने के कारण अस्वीकार किया गया। "
        "आपके {sourceA} पर नाम ({valueA}) आपके {sourceB} पर नाम ({valueB}) से मेल नहीं खाता। "
        "कृपया {correctionOffice} जाएं। "
        "प्रक्रिया: {correctionProcess}। अनुमानित समय: {estimatedTimeline}।"
    ),
    "mr": (
        "तुमचा अर्ज डेटा जुळत नसल्यामुळे नाकारला गेला. "
        "तुमच्या {sourceA} वरील नाव ({valueA}) तुमच्या {sourceB} वरील नाव ({valueB}) शी जुळत नाही. "
        "कृपया {correctionOffice} ला भेट द्या. "
        "प्रक्रिया: {correctionProcess}. अपेक्षित वेळ: {estimatedTimeline}."
    ),
}

CORRECTION_FORM_TEMPLATE = """
CORRECTION APPLICATION FORM
============================
To,
The {officeName}
{district}, Maharashtra

Date: {date}

Subject: Request for correction of {fieldLabel} in government records

Respected Sir/Madam,

I, {applicantName}, am writing to request a correction in my official records
in connection with my application for {scheme}.

MISMATCH DETAILS:
  Field           : {fieldLabel}
  Value in {sourceA} : {valueA}
  Value in {sourceB} : {valueB}
  Required Action : Update {sourceB} to match {sourceA}

I hereby submit the following supporting documents:
  1. Original {sourceA}
  2. Copy of {sourceB}
  3. Copy of rejection letter

I request you to kindly correct the above mismatch at the earliest.

Yours faithfully,
{applicantName}
Contact: _______________
Signature: _____________

(For office use)
Receipt No: ___________  Date: ___________  Officer: ___________
"""


def build_prompt(mismatches: list, scheme: str, lang: str) -> str:
    lang_name = LANG_NAMES.get(lang, "English")
    mismatch_text = "\n".join([
        f"- Field: {m['fieldLabel']}, In {m['sourceA']}: '{m['valueA']}', In {m['sourceB']}: '{m['valueB']}' (similarity: {m['similarityScore']}%)"
        for m in mismatches
    ])
    return f"""You are a helpful government assistance AI for India.

A citizen has been rejected from {scheme}. The following data mismatches were found:

{mismatch_text}

Please write a SHORT plain-language explanation in {lang_name} that:
1. Tells the citizen exactly what is wrong (field name, the two different values)
2. Tells them which office to go to: {mismatches[0].get('correctionOffice', 'Government Office') if mismatches else 'Government Office'}
3. Tells them what documents to bring
4. Tells them how many days it will take

Use simple words. No legal jargon. If writing in Hindi or Marathi, use Devanagari script.
Keep under 150 words."""


def call_bedrock(prompt: str) -> str:
    payload = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 512, "temperature": 0.3},
    }
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    body = json.loads(response["body"].read())
    return body["output"]["message"]["content"][0]["text"]


def build_fallback_diagnosis(mismatches: list, lang: str) -> str:
    if not mismatches:
        template = FALLBACK_DIAGNOSIS.get(lang, FALLBACK_DIAGNOSIS["en"])
        return template.format(
            sourceA="document A", valueA="value A",
            sourceB="document B", valueB="value B",
            correctionOffice="concerned government office",
            correctionProcess="contact issuing authority",
            estimatedTimeline="7-14 working days",
        )
    m = mismatches[0]
    template = FALLBACK_DIAGNOSIS.get(lang, FALLBACK_DIAGNOSIS["en"])
    return template.format(**m)


def build_correction_form(mismatches: list, scheme: str, applicant_name: str) -> str:
    import datetime
    if not mismatches:
        return "No mismatches found. No correction form needed."
    m = mismatches[0]
    return CORRECTION_FORM_TEMPLATE.format(
        officeName=m.get("correctionOffice", "Government Office"),
        district="Pune",
        date=datetime.date.today().strftime("%d/%m/%Y"),
        fieldLabel=m.get("fieldLabel", "Field"),
        applicantName=applicant_name,
        scheme=scheme,
        sourceA=m.get("sourceA", "Document A"),
        valueA=m.get("valueA", ""),
        sourceB=m.get("sourceB", "Document B"),
        valueB=m.get("valueB", ""),
    )


def lambda_handler(event, context):
    case_id = event.get("caseId")
    use_fallback = event.get("useFallback", False)
    lang = event.get("lang", "en")
    scheme = event.get("scheme", "PM-KISAN")
    applicant_name = event.get("applicantName", "Applicant")

    # Accept mismatches from Step Functions pass-through
    match_result = event.get("matchResult", {})
    mismatches = match_result.get("mismatches", event.get("mismatches", []))

    print(f"[generate] caseId={case_id} lang={lang} mismatches={len(mismatches)} fallback={use_fallback}")

    # ── Generate diagnosis ─────────────────────────────────────────
    diagnosis_en = ""
    diagnosis_hi = ""
    diagnosis_mr = ""

    if not use_fallback:
        try:
            diagnosis_en = call_bedrock(build_prompt(mismatches, scheme, "en"))
            diagnosis_hi = call_bedrock(build_prompt(mismatches, scheme, "hi"))
            diagnosis_mr = call_bedrock(build_prompt(mismatches, scheme, "mr"))
        except ClientError as e:
            print(f"[generate] Bedrock error: {e}. Using fallback.")
            use_fallback = True
        except Exception as e:
            print(f"[generate] Unexpected error: {e}. Using fallback.")
            use_fallback = True

    if use_fallback:
        diagnosis_en = build_fallback_diagnosis(mismatches, "en")
        diagnosis_hi = build_fallback_diagnosis(mismatches, "hi")
        diagnosis_mr = build_fallback_diagnosis(mismatches, "mr")

    # ── Generate correction form ───────────────────────────────────
    correction_form = build_correction_form(mismatches, scheme, applicant_name)

    result = {
        "caseId": case_id,
        "diagnosisEn": diagnosis_en,
        "diagnosisHi": diagnosis_hi,
        "diagnosisMr": diagnosis_mr,
        "correctionForm": correction_form,
        "usedFallback": use_fallback,
        "status": "Diagnosed",
    }

    # ── Store in DynamoDB ──────────────────────────────────────────
    if case_id:
        table.update_item(
            Key={"caseId": case_id},
            UpdateExpression="SET diagnosisEn = :e, diagnosisHi = :h, diagnosisMr = :m, correctionForm = :f, #s = :st, usedFallback = :fb",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":e": diagnosis_en,
                ":h": diagnosis_hi,
                ":m": diagnosis_mr,
                ":f": correction_form,
                ":st": "Diagnosed",
                ":fb": use_fallback,
            },
        )

    print(f"[generate] done. fallback={use_fallback}")
    return result
