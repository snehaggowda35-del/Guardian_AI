"""Optional managed model adapter. The model is advisory; policy gates remain local."""
import json
import httpx
from .config import get_settings

ALLOWED = {"normal", "emotional_distress", "bullying", "self_harm", "suicidal_risk", "violence", "threat", "exploitation", "dangerous_activity", "unknown"}

def analyze_text(text: str, context: list[str]) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    prompt = {
        "text": text,
        "recent_relevant_context": context[-3:],
        "instruction": "Classify meaning and safety intent, including indirect language and the language used. Do not diagnose. Return JSON only.",
    }
    body = {
        "model": settings.openai_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are a safety triage classifier. Output ONLY a JSON object with category (one of normal, emotional_distress, bullying, self_harm, suicidal_risk, violence, threat, exploitation, dangerous_activity, unknown), score (integer 0-100), confidence (number 0-1), and rationale (short neutral explanation). Treat figurative, quoted, fictional, academic, and negated language carefully. A high score is a signal for human review, never a diagnosis."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    }
    response = httpx.post(f"{settings.openai_base_url.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}, json=body, timeout=settings.ai_timeout_seconds)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    result = json.loads(content)
    category = result.get("category", "unknown")
    if category not in ALLOWED: category = "unknown"
    return {"category": category, "score": max(0, min(100, int(result.get("score", 0)))), "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.0)))), "rationale": str(result.get("rationale", "Model returned a safety signal for human review."))[:500]}
