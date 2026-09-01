#!/usr/bin/env python3
"""On-the-fly English vocabulary extraction for an article body, via a free
model on OpenRouter. Results are cached by server.py in db.vocab_cache so
each article only triggers one LLM call."""
import json
import os
import re

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
REQUIRED_FIELDS = ("term", "pos", "ipa", "zh", "example")

PROMPT_TEMPLATE = """You are helping a Cantonese-speaking reader learn English vocabulary through a Chinese-language opinion column.

Article title: {title}

Article body:
{body}

Pick 6 to 10 English words or phrases worth learning from this article: concepts, terms, or proper nouns (including Cantonese-transliterated names) tied to its subject matter. Skip vocabulary a learner would already know.

Respond with ONLY a JSON array, no other text, in this exact shape. The "zh" field must be written in Traditional Chinese (繁體中文), matching the article's own script — never Simplified Chinese:
[{{"term": "English word or phrase", "pos": "part of speech", "ipa": "/IPA pronunciation/", "zh": "the corresponding Traditional Chinese term or name from the article", "example": "one natural English sentence using the term, related to the article's topic"}}]
"""


class VocabError(Exception):
    pass


def generate_vocab(title, body):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise VocabError("OPENROUTER_API_KEY not configured")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": PROMPT_TEMPLATE.format(title=title, body=body)}
        ],
        "temperature": 0.4,
        "max_tokens": 1200,
        "reasoning": {"enabled": False},
        "provider": {"sort": "throughput"},
    }
    try:
        res = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=10,
        )
        if res.status_code == 400 and "reasoning is mandatory" in res.text.lower():
            # Some free-tier models can't have reasoning disabled and burn
            # 2000+ tokens on it regardless of any reasoning.max_tokens cap
            # — drop the toggle and retry with enough budget for both the
            # reasoning and the actual answer, and a timeout to match
            # (observed ~30-40s for minimax-m2.7:free).
            del payload["reasoning"]
            payload["max_tokens"] = 4000
            res = httpx.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=60,
            )
        res.raise_for_status()
    except httpx.HTTPError as e:
        raise VocabError(f"OpenRouter request failed: {e}") from e

    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise VocabError(f"unexpected OpenRouter response shape: {e}") from e

    return parse_terms(content)


def parse_terms(content):
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        raise VocabError(f"no JSON array found in model output: {content!r}")
    try:
        raw_terms = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise VocabError(f"invalid JSON from model: {e}") from e

    terms = [
        {field: str(t[field]) for field in REQUIRED_FIELDS}
        for t in raw_terms
        if isinstance(t, dict) and all(field in t for field in REQUIRED_FIELDS)
    ]
    if not terms:
        raise VocabError("model output had no valid terms")
    return terms
