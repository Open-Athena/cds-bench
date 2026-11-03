"""Strict CDS-bench answer comparison, independent of inference and reference solvers.

Records need the dataset's ``answer`` and ``output_format`` fields. The response
must end with the answer following a standalone ``Final answer:`` line. JSON key
order and equivalent numeric spellings are ignored; list order and values are
preserved. Scalar comparison ignores whitespace, except for numeric answers,
which are compared as finite decimals.
"""

import json
import re
from decimal import Decimal


def no_duplicate_keys(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError(f"duplicate object key: {key}")
        out[key] = value
    return out


def parse_json(text):
    return json.loads(
        text,
        object_pairs_hook=no_duplicate_keys,
        parse_float=Decimal,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("non-finite JSON number")),
    )


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) == type(b) and a == b
    if isinstance(a, (int, Decimal)) and isinstance(b, (int, Decimal)):
        return a == b
    if type(a) != type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(u, v) for u, v in zip(a, b))
    return a == b


def score(record, content):
    """Compare a complete assistant response with a dataset record."""
    markers = list(re.finditer(r"^Final answer:[ \t]*$", content, re.MULTILINE))
    if not markers:
        return {"passed": False, "format_ok": False, "error": "Missing exact final-answer marker"}
    final = content[markers[-1].end() :].strip()
    try:
        if record["output_format"] == "json":
            got = parse_json(final)
            want = parse_json(record["answer"])
            return {
                "passed": same(got, want),
                "format_ok": True,
                "final_answer": final,
                "parsed_answer": got,
            }
        try:
            want = parse_json(record["answer"])
        except (ValueError, TypeError):
            want = record["answer"]
        if isinstance(want, (int, Decimal)) and not isinstance(want, bool):
            got = Decimal(final)
            return {
                "passed": got.is_finite() and got == Decimal(want),
                "format_ok": True,
                "final_answer": final,
            }
        got = "".join(final.split())
        return {
            "passed": got == "".join(record["answer"].split()),
            "format_ok": True,
            "final_answer": final,
        }
    except (ValueError, TypeError, ArithmeticError) as error:
        return {"passed": False, "format_ok": False, "error": str(error), "final_answer": final}


def score_result(record, text, finish):
    """Apply strict scoring, treating token-limit completions as failures."""
    result = score(record, text)
    if finish == "length":
        result.update(passed=False, truncated=True)
    return result
