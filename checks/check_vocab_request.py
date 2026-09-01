#!/usr/bin/env python3
"""Verify vocab.generate_vocab sends the latency-bounding request params
(max_tokens cap, reasoning disabled, throughput-sorted provider, tight
timeout) to OpenRouter, falls back correctly for models that reject a
disabled reasoning toggle, and retries once (a fresh request, not just a
re-parse) when the model's output fails to parse. httpx.post is
monkeypatched so this never hits the network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

import vocab


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._payload


def main():
    real_post = httpx.post
    real_api_key = os.environ.get("OPENROUTER_API_KEY")

    fake_content = (
        '[{"term": "cabinet", "pos": "noun", "ipa": "/kab/", '
        '"zh": "內閣", "example": "The cabinet met."}]'
    )
    fake_ok = FakeResponse({"choices": [{"message": {"content": fake_content}}]})

    try:
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        # Normal path: single request, latency-bounding params present.
        calls = []

        def fake_post_ok(url, headers=None, json=None, timeout=None):
            calls.append((dict(json), timeout))
            return fake_ok

        httpx.post = fake_post_ok
        terms = vocab.generate_vocab("Title", "Body")
        assert len(terms) == 1, terms
        assert len(calls) == 1, calls

        sent, timeout = calls[0]
        assert sent["max_tokens"] == 1200, sent
        assert sent["reasoning"] == {"enabled": False}, sent
        assert sent["provider"] == {"sort": "throughput"}, sent
        assert timeout == 10, timeout

        # Mandatory-reasoning model: first call 400s, must retry without
        # the reasoning toggle and with a larger token/timeout budget.
        calls = []
        fake_400 = FakeResponse(
            {"error": {"message": "Reasoning is mandatory for this endpoint"}},
            status_code=400,
            text='{"error":{"message":"Reasoning is mandatory for this endpoint and cannot be disabled."}}',
        )

        def fake_post_retry(url, headers=None, json=None, timeout=None):
            calls.append((dict(json), timeout))
            return fake_400 if len(calls) == 1 else fake_ok

        httpx.post = fake_post_retry
        terms = vocab.generate_vocab("Title", "Body")
        assert len(terms) == 1, terms
        assert len(calls) == 2, calls

        first_sent, first_timeout = calls[0]
        assert first_sent["reasoning"] == {"enabled": False}, first_sent
        retry_sent, retry_timeout = calls[1]
        assert "reasoning" not in retry_sent, retry_sent
        assert retry_sent["max_tokens"] == 4000, retry_sent
        assert retry_timeout == 60, retry_timeout

        # Unparseable output (e.g. missing bracket, or genuinely no
        # recoverable terms) triggers exactly one fresh request+parse
        # retry, not just a re-parse of the same bad content.
        calls = []
        fake_garbage = FakeResponse(
            {"choices": [{"message": {"content": "I cannot help with that."}}]}
        )

        def fake_post_garbage_then_ok(url, headers=None, json=None, timeout=None):
            calls.append(1)
            return fake_garbage if len(calls) == 1 else fake_ok

        httpx.post = fake_post_garbage_then_ok
        terms = vocab.generate_vocab("Title", "Body")
        assert len(terms) == 1, terms
        assert len(calls) == 2, "should retry once on a parse failure, not give up immediately"

        # And it doesn't retry forever — two consecutive parse failures
        # should raise, not loop.
        calls = []

        def fake_post_always_garbage(url, headers=None, json=None, timeout=None):
            calls.append(1)
            return fake_garbage

        httpx.post = fake_post_always_garbage
        try:
            vocab.generate_vocab("Title", "Body")
            assert False, "expected VocabError when both attempts fail to parse"
        except vocab.VocabError:
            pass
        assert len(calls) == 2, "should stop after exactly one retry, not loop"

        print(
            "OK: vocab.generate_vocab caps max_tokens, disables reasoning, "
            "sorts by throughput, uses a 10s timeout, falls back correctly "
            "for mandatory-reasoning models, and retries once on a parse failure"
        )
    finally:
        httpx.post = real_post
        if real_api_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = real_api_key


if __name__ == "__main__":
    main()
