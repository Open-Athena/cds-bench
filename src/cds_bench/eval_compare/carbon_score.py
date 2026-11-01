"""Extract Carbon-X's final answer without changing its substantive contents.

Extraction depends only on model output and the declared output format. It never
reads a reference answer, searches for a matching candidate, computes an answer,
renames fields, reorders lists, or fixes sequence/numerical mistakes.
"""

import ast
import json
import re
from dataclasses import dataclass
from decimal import Decimal

from cds_bench.eval_luna.score import parse_json, score_result

VERSION = 'carbon-format-v1'
LABELS = [
    re.compile(r'(?im)^[ \t]*(?:#{1,6}[ \t]+)?(?P<decoration>\*\*|__|`)?(?:the[ \t]+)?final[ \t]+(?:answer|result)(?:\*\*|__|`)?(?:[ \t]*[:：][ \t]*|[ \t]+is[ \t]+|[ \t]*$)'),
    re.compile(r'(?im)^[ \t]*(?:#{1,6}[ \t]+)?(?P<decoration>\*\*|__|`)?answer(?:\*\*|__|`)?(?:[ \t]*[:：][ \t]*|[ \t]+is[ \t]+|[ \t]*$)'),
]
FENCE = re.compile(r'```(?:json|python|text)?[ \t]*\n(.*?)\n```', re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class NormalizedAnswer:
    answer: str
    changes: tuple[str, ...]


def unwrap(text):
    value = text.strip()
    for _ in range(3):
        fence = FENCE.fullmatch(value)
        if fence:
            value = fence[1].strip()
            continue
        changed = False
        for delimiter in ('**', '__', '`'):
            if value.startswith(delimiter) and value.endswith(delimiter) and len(value) > 2 * len(delimiter):
                value = value[len(delimiter):-len(delimiter)].strip()
                changed = True
                break
        if not changed:
            break
    return value


def literal_json(text):
    """Serialize literal Python data, preserving decimal digits and duplicate-key checks."""
    tree = ast.parse(text, mode='eval').body

    def render(node):
        if isinstance(node, ast.Dict):
            keys = [key.value if isinstance(key, ast.Constant) else None for key in node.keys]
            if any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys):
                raise ValueError('Object keys must be unique strings')
            return '{' + ','.join(json.dumps(key) + ':' + render(value) for key, value in zip(keys, node.values, strict=True)) + '}'
        if isinstance(node, ast.List):
            return '[' + ','.join(render(value) for value in node.elts) + ']'
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) or node.value is None or isinstance(node.value, bool):
                return json.dumps(node.value)
            if isinstance(node.value, int):
                return str(node.value)
            if isinstance(node.value, float):
                value = Decimal(ast.get_source_segment(text, node).replace('_', ''))
                if value.is_finite():
                    return str(value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            if isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float):
                value = Decimal(ast.get_source_segment(text, node).replace('_', ''))
                if value.is_finite():
                    return str(value)
        raise ValueError('Only JSON-shaped literal data are accepted')

    result = render(tree)
    parse_json(result)
    return result


def json_value(text):
    """Accept exactly one JSON value or JSON-shaped Python literal."""
    try:
        parse_json(text)
        return text, False
    except (ValueError, TypeError, ArithmeticError):
        return literal_json(text), True


def normalize_answer(text, output_format):
    value = text.strip()
    changes = []
    labelled = False
    for pattern in LABELS:
        labels = list(pattern.finditer(value))
        if labels:
            value = value[labels[-1].end():].strip()
            decoration = labels[-1].group('decoration')
            if decoration and value.startswith(decoration):
                value = value[len(decoration):].strip()
            changes.append('read_answer_after_label')
            labelled = True
            break
    value_without_tags = value.replace('<dna>', '').replace('</dna>', '')
    if value_without_tags != value:
        changes.append('remove_native_dna_tags')
        value = value_without_tags
    unwrapped = unwrap(value)
    if unwrapped != value:
        changes.append('remove_markdown_wrapper')
        value = unwrapped

    if output_format == 'json':
        try:
            value, python_literal = json_value(value)
            if python_literal:
                changes.append('python_literals_to_json')
            return NormalizedAnswer(value, tuple(changes))
        except (ValueError, TypeError, SyntaxError, ArithmeticError):
            pass
        # A last fenced answer or complete trailing container has a definite
        # boundary. Choose by position and syntax, never by reference/scoring.
        fences = list(FENCE.finditer(value))
        if fences and value[fences[-1].end():].strip() in ('', '.'):
            candidate, python_literal = json_value(fences[-1][1].strip())
            changes.append('read_final_code_block')
            if python_literal:
                changes.append('python_literals_to_json')
            return NormalizedAnswer(candidate, tuple(changes))
        for position, char in enumerate(value):
            if char not in '[{':
                continue
            try:
                candidate, python_literal = json_value(value[position:].strip())
            except (ValueError, TypeError, SyntaxError, ArithmeticError):
                continue
            changes.append('read_complete_trailing_json')
            if python_literal:
                changes.append('python_literals_to_json')
            return NormalizedAnswer(candidate, tuple(changes))
    elif output_format == 'scalar':
        fences = list(FENCE.finditer(value))
        if fences and value[fences[-1].end():].strip() in ('', '.'):
            value = fences[-1][1].strip()
            changes.append('read_final_code_block')
        if labelled:
            fence = FENCE.fullmatch(value.rstrip('.').strip())
            if fence:
                value = fence[1].strip()
                changes.append('remove_markdown_wrapper')
        # Quotes around an entire scalar are presentation, not sequence data.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            try:
                decoded = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                decoded = None
            if isinstance(decoded, str):
                value = decoded
                changes.append('unquote_scalar')
        if value.casefold() == 'impossible':
            value = 'IMPOSSIBLE'
            changes.append('normalize_impossible_capitalization')
    return NormalizedAnswer(value, tuple(changes))


def score_normalized(record, text, finish):
    strict = score_result(record, text, finish)
    if finish == 'length':
        return {'strict_passed': strict['passed'], 'strict_format_ok': strict.get('format_ok'),
                'passed': False, 'truncated': True, 'format_ok': strict.get('format_ok', False),
                'normalization_version': VERSION, 'normalization_changes': [],
                'error': 'Generated-token budget exhausted'}
    try:
        normalized = normalize_answer(text, record['output_format'])
        relaxed = score_result(record, 'Final answer:\n' + normalized.answer, finish)
    except (ValueError, TypeError, SyntaxError, ArithmeticError, RecursionError) as exc:
        normalized = NormalizedAnswer(text, ())
        relaxed = {'passed': False, 'format_ok': False, 'error': str(exc)}
    return {**relaxed, 'strict_passed': strict['passed'], 'strict_format_ok': strict.get('format_ok'),
            'normalization_version': VERSION, 'normalization_changes': list(normalized.changes),
            'normalized_answer': normalized.answer}
