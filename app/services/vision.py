"""Classifies an uploaded photo into a safety/facility issue category and
severity using Groq (free tier, OpenAI-compatible vision API).

If the AI call fails for ANY reason (no key, rate limit, bad response, network),
a safe fallback result is returned, so creating a report never fails because
of the AI. The severity can then be corrected manually."""
import base64
import json
import logging
import mimetypes
import traceback
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    is_valid_issue: bool
    category: str
    severity: str
    confidence: float
    description: str


VALID_CATEGORIES = [
    "SAFETY_HAZARD", "EQUIPMENT_FAULT", "QUALITY_DEFECT",
    "CLEANLINESS", "FIRE_SAFETY", "ELECTRICAL", "OTHER",
]
VALID_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

PROMPT = (
    "You are inspecting a worker-submitted photo from a factory/facility "
    "safety reporting app. Respond ONLY with JSON (no markdown): "
    '{"is_valid_issue": bool, '
    '"category": one of ["SAFETY_HAZARD","EQUIPMENT_FAULT","QUALITY_DEFECT",'
    '"CLEANLINESS","FIRE_SAFETY","ELECTRICAL","OTHER"], '
    '"severity": one of ["CRITICAL","HIGH","MEDIUM","LOW"], '
    '"confidence": float 0-1, "description": short factual description}. '
    "Severity CRITICAL means immediate risk to life or major equipment damage."
)


def _fallback(description: str) -> ClassificationResult:
    logger.warning("Returning FALLBACK classification result: %s", description)
    return ClassificationResult(
        is_valid_issue=True,
        category="OTHER",
        severity="MEDIUM",
        confidence=0.5,
        description=description,
    )


async def classify_photo(photo_path: str) -> ClassificationResult:
    logger.info("=== [VISION AI START] ===")
    logger.info("Received photo_path: %s", photo_path)
    logger.info("GROQ_API_KEY configured: %s", bool(settings.groq_api_key))

    if not settings.groq_api_key:
        logger.warning("No GROQ_API_KEY set in environment! Skipping classification.")
        return _fallback("[stub] No GROQ_API_KEY set - skipping real classification.")

    try:
        # 1. Handle Cloudinary HTTPS URL or Web URL
        if photo_path and (photo_path.startswith("http://") or photo_path.startswith("https://")):
            logger.info("Detected Web/Cloudinary URL. Downloading image via HTTP...")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(photo_path)
                logger.info("Download Status Code: %s", resp.status_code)
                resp.raise_for_status()
                image_bytes = resp.content
                mime_type = resp.headers.get("content-type", "image/jpeg")
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            logger.info("Successfully fetched and base64 encoded image from URL.")

        # 2. Handle Local File Path
        else:
            logger.info("Detected local file path. Attempting to open from disk...")
            with open(photo_path, "rb") as f:
                image_bytes = f.read()
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            mime_type = mimetypes.guess_type(photo_path)[0] or "image/jpeg"
            logger.info("Successfully loaded local file.")

        return await _call_vision_model(image_b64, mime_type)

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        logger.error("HTTP Exception while fetching image or calling Groq: %s", e)
        logger.error("Response body: %s", e.response.text[:300])
        reason = "Groq rate limit or quota reached (429)." if status == 429 else f"HTTP error ({status})."
        return _fallback(f"[fallback] {reason} Severity not classified by AI.")
    except Exception as e:
        logger.error("EXCEPTIONAL ERROR in classify_photo: %r", e)
        logger.error("FULL TRACEBACK:\n%s", traceback.format_exc())
        return _fallback(
            f"[fallback] AI classification failed ({type(e).__name__}: {str(e)}). "
            "Severity not classified by AI."
        )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


async def _call_vision_model(image_b64: str, mime_type: str) -> ClassificationResult:
    # Ensure model fallback if settings parameter is missing
    model_name = getattr(settings, "groq_model", None) or "llama-3.2-11b-vision-preview"
    logger.info("Calling Groq Vision API with model: %s", model_name)

    groq_endpoint_url = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            groq_endpoint_url,
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model_name,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}"
                        }},
                    ],
                }],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
        )
    logger.info("Groq API Response Status: %s", response.status_code)
    response.raise_for_status()

    raw_text = response.json()["choices"][0]["message"]["content"]
    logger.info("Groq Raw Response Content: %s", raw_text)

    parsed = json.loads(_strip_fences(raw_text))

    category = parsed.get("category")
    category = category if category in VALID_CATEGORIES else "OTHER"
    severity = parsed.get("severity")
    severity = severity if severity in VALID_SEVERITIES else "MEDIUM"

    try:
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    result = ClassificationResult(
        is_valid_issue=bool(parsed.get("is_valid_issue", True)),
        category=category,
        severity=severity,
        confidence=confidence,
        description=str(parsed.get("description", "")),
    )
    logger.info("=== [VISION AI SUCCESS] Result: %s ===", result)
    return result


















# """Classifies an uploaded photo into a safety/facility issue category and
# severity using Groq (free tier, OpenAI-compatible vision API).

# If the AI call fails for ANY reason (no key, rate limit, bad response, network),
# a safe fallback result is returned, so creating a report never fails because
# of the AI. The severity can then be corrected manually."""
# import base64
# import json
# import logging
# import mimetypes
# from dataclasses import dataclass

# import httpx

# from app.core.config import settings

# logger = logging.getLogger(__name__)


# @dataclass
# class ClassificationResult:
#     is_valid_issue: bool
#     category: str
#     severity: str
#     confidence: float
#     description: str


# VALID_CATEGORIES = [
#     "SAFETY_HAZARD", "EQUIPMENT_FAULT", "QUALITY_DEFECT",
#     "CLEANLINESS", "FIRE_SAFETY", "ELECTRICAL", "OTHER",
# ]
# VALID_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# PROMPT = (
#     "You are inspecting a worker-submitted photo from a factory/facility "
#     "safety reporting app. Respond ONLY with JSON (no markdown): "
#     '{"is_valid_issue": bool, '
#     '"category": one of ["SAFETY_HAZARD","EQUIPMENT_FAULT","QUALITY_DEFECT",'
#     '"CLEANLINESS","FIRE_SAFETY","ELECTRICAL","OTHER"], '
#     '"severity": one of ["CRITICAL","HIGH","MEDIUM","LOW"], '
#     '"confidence": float 0-1, "description": short factual description}. '
#     "Severity CRITICAL means immediate risk to life or major equipment damage."
# )


# def _fallback(description: str) -> ClassificationResult:
#     return ClassificationResult(
#         is_valid_issue=True,
#         category="OTHER",
#         severity="MEDIUM",
#         confidence=0.5,
#         description=description,
#     )


# async def classify_photo(photo_path: str) -> ClassificationResult:
#     if not settings.groq_api_key:
#         return _fallback("[stub] No GROQ_API_KEY set - skipping real classification.")

#     try:
#         with open(photo_path, "rb") as f:
#             image_b64 = base64.b64encode(f.read()).decode("utf-8")
#         mime_type = mimetypes.guess_type(photo_path)[0] or "image/jpeg"
#         return await _call_vision_model(image_b64, mime_type)
#     except httpx.HTTPStatusError as e:
#         status = e.response.status_code
#         logger.warning("Groq API error %s: %s", status, e.response.text[:300])
#         reason = "Groq rate limit or quota reached (429)." if status == 429 else f"Groq API error ({status})."
#         return _fallback(f"[fallback] {reason} Severity not classified by AI.")
#     except Exception as e:
#         logger.warning("Vision classification failed: %r", e)
#         return _fallback(
#             f"[fallback] AI classification failed ({type(e).__name__}). "
#             "Severity not classified by AI."
#         )


# def _strip_fences(text: str) -> str:
#     text = text.strip()
#     if text.startswith("```"):
#         text = text.strip("`")
#         if text.lower().startswith("json"):
#             text = text[4:]
#     return text.strip()


# async def _call_vision_model(image_b64: str, mime_type: str) -> ClassificationResult:
#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(
#             "https://api.groq.com/openai/v1/chat/completions",
#             headers={"Authorization": f"Bearer {settings.groq_api_key}"},
#             json={
#                 "model": settings.groq_model,
#                 "messages": [{
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": PROMPT},
#                         {"type": "image_url", "image_url": {
#                             "url": f"data:{mime_type};base64,{image_b64}"
#                         }},
#                     ],
#                 }],
#                 "response_format": {"type": "json_object"},
#                 "temperature": 0.2,
#             },
#         )
#     response.raise_for_status()

#     text = response.json()["choices"][0]["message"]["content"]
#     parsed = json.loads(_strip_fences(text))

#     category = parsed.get("category")
#     category = category if category in VALID_CATEGORIES else "OTHER"
#     severity = parsed.get("severity")
#     severity = severity if severity in VALID_SEVERITIES else "MEDIUM"

#     try:
#         confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
#     except (TypeError, ValueError):
#         confidence = 0.5

#     return ClassificationResult(
#         is_valid_issue=bool(parsed.get("is_valid_issue", True)),
#         category=category,
#         severity=severity,
#         confidence=confidence,
#         description=str(parsed.get("description", "")),
#     )













# """Classifies an uploaded photo into a safety/facility issue category and
# severity using Google Gemini (free tier). Only this file needs to change to
# swap providers.

# If the AI call fails for ANY reason (no key, rate limit, bad response, network),
# a safe fallback result is returned, so creating a report never fails because
# of the AI. The severity can then be corrected manually."""
# import base64
# import json
# import logging
# import mimetypes
# from dataclasses import dataclass

# import httpx

# from app.core.config import settings

# logger = logging.getLogger(__name__)


# @dataclass
# class ClassificationResult:
#     is_valid_issue: bool
#     category: str   # matches Prisma ReportCategory enum values
#     severity: str   # matches Prisma Severity enum values
#     confidence: float
#     description: str


# VALID_CATEGORIES = [
#     "SAFETY_HAZARD", "EQUIPMENT_FAULT", "QUALITY_DEFECT",
#     "CLEANLINESS", "FIRE_SAFETY", "ELECTRICAL", "OTHER",
# ]
# VALID_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# PROMPT = (
#     "You are inspecting a worker-submitted photo from a factory/facility "
#     "safety reporting app. Respond ONLY with JSON (no markdown): "
#     '{"is_valid_issue": bool, '
#     '"category": one of ["SAFETY_HAZARD","EQUIPMENT_FAULT","QUALITY_DEFECT",'
#     '"CLEANLINESS","FIRE_SAFETY","ELECTRICAL","OTHER"], '
#     '"severity": one of ["CRITICAL","HIGH","MEDIUM","LOW"], '
#     '"confidence": float 0-1, "description": short factual description}. '
#     "Severity CRITICAL means immediate risk to life or major equipment damage."
# )


# def _fallback(description: str) -> ClassificationResult:
#     return ClassificationResult(
#         is_valid_issue=True,
#         category="OTHER",
#         severity="MEDIUM",
#         confidence=0.5,
#         description=description,
#     )


# async def classify_photo(photo_path: str) -> ClassificationResult:
#     if not settings.gemini_api_key:
#         return _fallback("[stub] No GEMINI_API_KEY set - skipping real classification.")

#     try:
#         with open(photo_path, "rb") as f:
#             image_b64 = base64.b64encode(f.read()).decode("utf-8")
#         mime_type = mimetypes.guess_type(photo_path)[0] or "image/jpeg"
#         return await _call_vision_model(image_b64, mime_type)
#     except httpx.HTTPStatusError as e:
#         status = e.response.status_code
#         logger.warning("Gemini API error %s: %s", status, e.response.text[:300])
#         if status == 429:
#             reason = "Gemini rate limit or quota reached (429)."
#         else:
#             reason = f"Gemini API error ({status})."
#         return _fallback(f"[fallback] {reason} Severity not classified by AI.")
#     except Exception as e:  # network error, bad JSON, missing file, ...
#         logger.warning("Vision classification failed: %r", e)
#         return _fallback(
#             f"[fallback] AI classification failed ({type(e).__name__}). "
#             "Severity not classified by AI."
#         )


# def _strip_fences(text: str) -> str:
#     text = text.strip()
#     if text.startswith("```"):
#         text = text.strip("`")
#         if text.lower().startswith("json"):
#             text = text[4:]
#     return text.strip()


# async def _call_vision_model(image_b64: str, mime_type: str) -> ClassificationResult:
#     url = (
#         "https://generativelanguage.googleapis.com/v1beta/models/"
#         f"{settings.gemini_model}:generateContent"
#     )

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(
#             url,
#             headers={"x-goog-api-key": settings.gemini_api_key},
#             json={
#                 "contents": [
#                     {
#                         "parts": [
#                             {"text": PROMPT},
#                             {"inline_data": {"mime_type": mime_type, "data": image_b64}},
#                         ]
#                     }
#                 ],
#                 "generationConfig": {
#                     "responseMimeType": "application/json",
#                     "temperature": 0.2,
#                 },
#             },
#         )
#     response.raise_for_status()

#     parts = response.json()["candidates"][0]["content"]["parts"]
#     text = "".join(p.get("text", "") for p in parts)
#     parsed = json.loads(_strip_fences(text))

#     category = parsed.get("category")
#     category = category if category in VALID_CATEGORIES else "OTHER"
#     severity = parsed.get("severity")
#     severity = severity if severity in VALID_SEVERITIES else "MEDIUM"

#     try:
#         confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
#     except (TypeError, ValueError):
#         confidence = 0.5

#     return ClassificationResult(
#         is_valid_issue=bool(parsed.get("is_valid_issue", True)),
#         category=category,
#         severity=severity,
#         confidence=confidence,
#         description=str(parsed.get("description", "")),
#     )