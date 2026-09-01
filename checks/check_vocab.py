#!/usr/bin/env python3
"""Verify vocab.parse_terms handles well-formed, prose-wrapped, malformed,
and response_format-conforming ({"terms": [...]}) model output correctly."""
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

    # Observed in production: the model completes every object correctly
    # but omits the array's closing ']'. The strict array-regex path can't
    # match this at all (no closing bracket anywhere), but every object is
    # individually valid and should still be recovered.
    missing_closing_bracket = (
        '[\n{"term": "veto", "pos": "noun", "ipa": "/v/", "zh": "否決", "example": "x"},\n'
        '{"term": "cabinet", "pos": "noun", "ipa": "/kab/", "zh": "內閣", "example": "y"}'
    )
    recovered = vocab.parse_terms(missing_closing_bracket)
    assert len(recovered) == 2, recovered
    assert recovered[0]["term"] == "veto" and recovered[1]["term"] == "cabinet", recovered

    # Braces inside a string value (e.g. an example sentence quoting code
    # or JSON) shouldn't throw off the lenient path's depth tracking.
    brace_in_string_value = (
        '[{"term": "veto", "pos": "noun", "ipa": "/v/", "zh": "否決", '
        '"example": "She said \\"use {curly braces}\\" in the example."}'
    )
    recovered = vocab.parse_terms(brace_in_string_value)
    assert len(recovered) == 1 and recovered[0]["term"] == "veto", recovered

    # Truly empty/garbage output still raises, even with the lenient path.
    garbage = "I cannot complete this request."
    try:
        vocab.parse_terms(garbage)
        assert False, "expected VocabError for garbage output"
    except vocab.VocabError:
        pass

    # response_format's requested shape: a pure JSON object, not an array.
    schema_conforming = (
        '{"terms": [{"term": "cabinet", "pos": "noun", "ipa": "/kab/", '
        '"zh": "內閣", "example": "The cabinet met."}]}'
    )
    assert vocab.parse_terms(schema_conforming) == terms

    # A provider that partially honors response_format (or ignores it and
    # wraps in prose) but still omits the terms array's closing bracket —
    # the wrapper object itself has no term/pos/etc fields and should be
    # dropped, while the nested term object is still recovered.
    schema_conforming_missing_bracket = (
        'Here is the JSON: {"terms": [{"term": "veto", "pos": "noun", '
        '"ipa": "/v/", "zh": "否決", "example": "x"}'
    )
    recovered = vocab.parse_terms(schema_conforming_missing_bracket)
    assert len(recovered) == 1 and recovered[0]["term"] == "veto", recovered

    print("OK: vocab.parse_terms handles clean, wrapped, malformed, bracket-missing, and schema-conforming model output")


if __name__ == "__main__":
    main()
