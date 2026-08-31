#!/usr/bin/env python3
"""Verify vocab.generate_vocab sends the latency-bounding request params
(max_tokens cap, reasoning disabled) to OpenRouter. httpx.post is
monkeypatched so this never hits the network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

import vocab


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def main():
    calls = []
    real_post = httpx.post
    real_api_key = os.environ.get("OPENROUTER_API_KEY")

    fake_content = (
        '[{"term": "cabinet", "pos": "noun", "ipa": "/kab/", '
        '"zh": "內閣", "example": "The cabinet met."}]'
    )

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return FakeResponse({"choices": [{"message": {"content": fake_content}}]})

    try:
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        httpx.post = fake_post

        terms = vocab.generate_vocab("Title", "Body")
        assert len(terms) == 1, terms
        assert len(calls) == 1, calls

        sent = calls[0]
        assert sent["max_tokens"] == 1200, sent
        assert sent["reasoning"] == {"enabled": False}, sent

        print("OK: vocab.generate_vocab caps max_tokens and disables reasoning")
    finally:
        httpx.post = real_post
        if real_api_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = real_api_key


if __name__ == "__main__":
    main()
