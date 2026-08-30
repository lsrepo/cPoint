#!/usr/bin/env python3
"""Verify vocab.parse_terms handles well-formed, prose-wrapped, and
malformed model output correctly."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vocab


def main():
    clean = '[{"term": "cabinet", "pos": "noun", "ipa": "/kab/", "zh": "內閣", "example": "The cabinet met."}]'
    terms = vocab.parse_terms(clean)
    assert terms == [{"term": "cabinet", "pos": "noun", "ipa": "/kab/", "zh": "內閣", "example": "The cabinet met."}], terms

    prose_wrapped = f"Here you go:\n{clean}\nHope that helps!"
    assert vocab.parse_terms(prose_wrapped) == terms

    missing_field = '[{"term": "veto", "pos": "noun"}]'
    try:
        vocab.parse_terms(missing_field)
        assert False, "expected VocabError for missing fields"
    except vocab.VocabError:
        pass

    no_array = "Sorry, I can't help with that."
    try:
        vocab.parse_terms(no_array)
        assert False, "expected VocabError for missing JSON array"
    except vocab.VocabError:
        pass

    invalid_json = "[{term: cabinet}]"
    try:
        vocab.parse_terms(invalid_json)
        assert False, "expected VocabError for invalid JSON"
    except vocab.VocabError:
        pass

    mixed_valid = (
        '[{"term": "veto", "pos": "noun", "ipa": "/v/", "zh": "否決", "example": "x"}, '
        '{"term": "bad"}]'
    )
    assert len(vocab.parse_terms(mixed_valid)) == 1

    print("OK: vocab.parse_terms handles clean, wrapped, and malformed model output")


if __name__ == "__main__":
    main()
