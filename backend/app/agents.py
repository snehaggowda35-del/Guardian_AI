"""Deterministic prototype workflow. Replace classifier/heuristics with validated models before production."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import re
import unicodedata
from typing import Iterable
from .config import get_settings
from .ai_provider import analyze_text

logger = logging.getLogger(__name__)

RULES = {
    "suicidal_risk": (["don't want to be alive", "do not want to be alive", "want to die", "kill myself", "hang myself", "hanging myself", "strangle myself", "choke myself", "end my life", "suicide", "suicidal", "feeling suicidal", "feel suicidal", "no reason to live", "better off dead", "disappear forever"], 82),
    "self_harm": (["hurt myself", "cut myself", "self harm", "self-harm", "harm myself", "ways to hurt", "how to cut", "make myself bleed"], 76),
    "violence": (["kill him", "kill her", "kill someone", "kill everybody", "i'll kill", "ill kill", "going to kill", "want to kill", "murder", "murder someone", "want to murder", "going to murder", "shoot", "bring a weapon", "hurt you", "stab", "attack them"], 70),
    "exploitation": (["send nudes", "keep this secret from your parents", "meet me alone", "don't tell anyone", "do not tell anyone"], 66),
    "bullying": (["everyone hates me", "being bullied", "they keep calling me", "no one will leave me alone", "they are threatening me"], 48),
    "emotional_distress": (["feel hopeless", "nobody cares", "feel empty", "can't take this anymore", "cannot take this anymore", "feel useless", "i am alone", "i'm alone", "nothing matters"], 42),
    "dangerous_activity": (["how to make a bomb", "dangerous challenge", "how to make a weapon", "how to poison"], 65),
}
BENIGN = ["dying laughing", "die laughing", "dead laughing", "history of suicide", "suicide prevention", "history of murder", "murder mystery", "murder in fiction", "book report", "movie", "algorithm", "fictional character"]

def normalize(text: str) -> str:
    """Normalize user text without attempting to infer or store unrelated page content."""
    value = unicodedata.normalize("NFKC", text).casefold()
    value = value.replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()

def negated(text: str, phrase: str) -> bool:
    """Conservative local negation check for common English safety disclaimers."""
    start = text.find(phrase)
    if start < 0: return False
    window = text[max(0, start - 24):start]
    return bool(re.search(r"\b(no|not|never|without)\s+(?:feeling\s+)?$", window))

@dataclass
class Assessment:
    category: str; score: int; confidence: float; severity: str; alert: bool; rationale: str; context: list[str]; decisions: list[tuple[str, str, str]]

def classify(text: str) -> tuple[str, int, float]:
    normalized = normalize(text)
    if any(term in normalized for term in BENIGN): return "normal", 0, .94
    matches = [(category, base, phrase) for category, (phrases, base) in RULES.items() for phrase in phrases if phrase in normalized and not negated(normalized, phrase)]
    if not matches: return "normal", 0, .90
    category, score, _ = max(matches, key=lambda match: match[1])
    return category, score, min(.98, .72 + (len(matches) * .08))

def _rules_assess(text: str, history: Iterable[object]) -> Assessment:
    category, base_score, confidence = classify(text)
    decisions = [("Detection Agent", category, "Screened normalized text with the deterministic safety baseline (model version rules-v2).")]
    if category == "normal":
        return Assessment(category, 0, confidence, "LOW", False, "No safety signal detected; the event was minimized and not retained.", [], decisions)
    relevant = [event.trigger_text for event in history if event.category != "normal"][-3:]
    decisions.append(("Context Agent", f"{len(relevant)} relevant events", "Used only a short, 24-hour safety-relevant context window."))
    escalating = len(relevant) >= 2 or any("hurt myself" in item.lower() or "alive" in item.lower() for item in relevant)
    score = min(100, base_score + (12 if relevant else 0) + (8 if escalating else 0))
    if score >= 81: severity = "CRITICAL"
    elif score >= 61: severity = "HIGH"
    elif score >= 31: severity = "MODERATE"
    else: severity = "LOW"
    decisions += [
        ("Risk Agent", severity, f"Base score {base_score}, adjusted to {score} using limited context."),
        ("Escalation Agent", "increasing" if escalating else "stable", "Repeated related signals increase concern." if escalating else "No escalating pattern found."),
        ("Privacy Agent", "selective disclosure", "Only trigger text and up to three relevant events may be shown to the parent."),
    ]
    alert = severity in {"HIGH", "CRITICAL"}
    decisions.append(("Decision Agent", "ALERT_PARENT" if alert else "MONITOR", "Deterministic threshold policy; parent retains final judgment."))
    rationale = f"Potential {category.replace('_', ' ')} signal. " + ("Related recent signals suggest an increasing pattern." if escalating else "No broader escalation pattern was found.")
    return Assessment(category, score, confidence, severity, alert, rationale, relevant, decisions)

def assess(text: str, history: Iterable[object]) -> Assessment:
    """Use a configured managed model when available, with deterministic fallback."""
    history_list = list(history)
    settings = get_settings()
    if settings.ai_provider.lower() == "openai" and settings.openai_api_key:
        relevant = [event.trigger_text for event in history_list if event.category != "normal"][-3:]
        try:
            model = analyze_text(text, relevant)
            category, score, confidence = model["category"], model["score"], model["confidence"]
            if category == "normal" or score < 31:
                return Assessment("normal", 0, confidence, "LOW", False, "No safety signal detected; the event was minimized and not retained.", [], [("Detection Agent", "normal", "Managed multilingual model found no safety signal.")])
            severity = "CRITICAL" if score >= 81 else "HIGH" if score >= 61 else "MODERATE" if score >= 31 else "LOW"
            escalating = len(relevant) >= 2
            decisions = [("Detection Agent", category, "Managed multilingual model screened meaning, intent, and language."), ("Context Agent", f"{len(relevant)} relevant events", "Used only a short, 24-hour safety-relevant context window."), ("Risk Agent", severity, f"Model score {score}; deterministic severity threshold applied."), ("Escalation Agent", "increasing" if escalating else "stable", "Repeated related signals increase concern." if escalating else "No escalating pattern found."), ("Privacy Agent", "selective disclosure", "Only trigger text and up to three relevant events may be shown to the parent."), ("Decision Agent", "ALERT_PARENT" if severity in {"HIGH", "CRITICAL"} else "MONITOR", "Deterministic threshold policy; parent retains final judgment.")]
            return Assessment(category, score, confidence, severity, severity in {"HIGH", "CRITICAL"}, model["rationale"], relevant, decisions)
        except Exception as error:
            # A provider outage must not silently block ingestion; fall back to the auditable local baseline.
            logger.warning("Managed AI analysis failed; using rules-v2 fallback: %s", error)
    return _rules_assess(text, history_list)
