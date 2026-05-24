import requests
import logging
from config import (
    LLM_PROVIDER,
    OLLAMA_MODEL, 
    OLLAMA_TIMEOUT_SECONDS, 
    OLLAMA_URL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEEPSEEK_URL,
)


LOGGER = logging.getLogger(__name__)


def _build_prompt(context, emotion, intent, risk):
    base = f"""
    You are an AI assistive communication support system.

    Context: {context}
    Detected Emotion: {emotion}
    Inferred Intent: {intent}
    Risk Level: {risk}
    """

    if context == "hr":
        role_rules = """
        Task:
        - Provide one short, practical interviewer coaching suggestion.
        Constraints:
        - Do not suggest hire/reject decisions or personality judgments.
        - Keep the guidance neutral, fair, and action-oriented.
        - Keep it under 2 sentences.
        """
    elif context == "teacher":
        role_rules = """
        Task:
        - Provide one short classroom coaching suggestion for the teacher.
        Constraints:
        - Focus on engagement, clarity, pacing, or low-pressure checks for understanding.
        - During assessment stress, suggest de-escalation and fair monitoring steps.
        - Keep it under 2 sentences.
        """
    elif context == "doctor":
        role_rules = """
        Task:
        - Provide one short, clinically safe communication suggestion for patient care.
        Constraints:
        - Do not diagnose; suggest supportive communication and escalation checks only.
        - Prioritize calm, safety, and clear caregiver actions when risk is elevated.
        - Keep it under 2 sentences.
        """
    else:
        role_rules = """
        Task:
        - Provide one short, professional, context-aware communication suggestion.
        Constraints:
        - Keep it under 2 sentences.
        """

    return f"{base}\n{role_rules}"


def _fallback_suggestion(context, emotion, risk):
    if context == "doctor":
        if risk in {"high", "medium"}:
            return f"Pause and check patient comfort; acknowledge the detected {emotion} cues and ask one calming, closed question."
        return "Maintain supportive communication and continue routine observation."
    if context == "teacher":
        if risk in {"high", "medium"}:
            return f"Slow the pace, confirm understanding privately, and provide a short scaffolded prompt for the detected {emotion} state."
        return "Continue instruction and reinforce engagement with brief checks for understanding."
    if context == "hr":
        if risk in {"high", "medium"}:
            return f"Shift to a clarifying question, reduce pressure, and offer a brief pause given the detected {emotion} state."
        return "Proceed with structured questions while maintaining a calm and neutral tone."
    return "Maintain clear, supportive communication and monitor changes."


def _generate_ollama_suggestion(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except Exception as exc:
        LOGGER.warning("Ollama request failed: %s", exc)
        return None


def _generate_deepseek_suggestion(prompt):
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_key_here":
        LOGGER.warning("DeepSeek API Key missing or default.")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "You are an assistive communication AI. Provide short, practical coaching suggestions based on detected human intent."},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        response = requests.post(
            DEEPSEEK_URL,
            json=payload,
            headers=headers,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except Exception as exc:
        LOGGER.warning("DeepSeek request failed: %s", exc)
        return None


def generate_suggestion(context, emotion, intent, risk):
    prompt = _build_prompt(context, emotion, intent, risk)
    
    suggestion = None
    if LLM_PROVIDER == "deepseek":
        suggestion = _generate_deepseek_suggestion(prompt)
    
    # Fallback to Ollama if deepseek fails or is not selected
    if not suggestion:
        suggestion = _generate_ollama_suggestion(prompt)
    
    # Final fallback to static rules if everything fails
    return suggestion or _fallback_suggestion(context, emotion, risk)
