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

    content = _request_completion(api_key, model, title, body)
    try:
        return parse_terms(content)
    except VocabError:
        # Malformed/incomplete JSON is usually just sampling variance
        # (temperature 0.4) rather than a systemic issue — a fresh
        # attempt often succeeds where the first didn't. One retry only;
        # if this also fails, let the VocabError propagate normally.
        content = _request_completion(api_key, model, title, body)
        return parse_terms(content)


def _request_completion(api_key, model, title, body):
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
        return res.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise VocabError(f"unexpected OpenRouter response shape: {e}") from e


def parse_terms(content):
    if content is None:
        raise VocabError("empty content from model")

    terms = _parse_strict(content) or _parse_lenient(content)
    if not terms:
        raise VocabError(f"no valid vocab terms found in model output: {content!r}")
    return terms


def _parse_strict(content):
    """The happy path: content is (or contains) one well-formed JSON array."""
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        return None
    try:
        raw_terms = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return _coerce_terms(raw_terms)


def _parse_lenient(content):
    """Fallback for output that's individually valid but not a well-formed
    array — most commonly a missing closing ']' (observed in practice:
    the model completes 10 correct objects and just omits it). Recovers
    whichever top-level {...} objects parse, ignoring the array wrapper
    entirely."""
    raw_terms = []
    for obj_str in _extract_json_objects(content):
        try:
            raw_terms.append(json.loads(obj_str))
        except json.JSONDecodeError:
            continue
    return _coerce_terms(raw_terms)


def _extract_json_objects(content):
    """Scan for top-level balanced {...} substrings, string-literal-aware
    so braces inside quoted text don't throw off the depth count."""
    objects = []
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(content):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    objects.append(content[start:i + 1])
                    start = None
    return objects


def _coerce_terms(raw_terms):
    return [
        {field: str(t[field]) for field in REQUIRED_FIELDS}
        for t in raw_terms
        if isinstance(t, dict) and all(field in t for field in REQUIRED_FIELDS)
    ]
