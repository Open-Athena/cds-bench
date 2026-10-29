"""Read the published definitions and exact prompt templates without editing them."""

import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = (ROOT / "index.html").read_text()
SPEC_SHA256 = hashlib.sha256(SPEC.encode()).hexdigest()
DATA = json.loads(
    re.search(r'<script type="application/json" id="task-data">(.*?)</script>', SPEC, re.DOTALL)[1]
)
TASKS = {
    t.get("task_type", t.get("composition_type")): t for t in DATA["tasks"] + DATA["compositions"]
}


def _template(task_id: str, variant: str) -> str | None:
    prefix = "composition" if task_id.startswith(("pipeline.", "joint.")) else "task"
    element = f"{prefix}-{task_id}-{variant}"
    match = re.search(
        r'<pre[^>]*id="' + re.escape(element) + r'"[^>]*><code>(.*?)</code></pre>', SPEC, re.DOTALL
    )
    return html.unescape(match[1]).strip() if match else None


def template(task_id: str, variant: str) -> str:
    prompt = _template(task_id, variant)
    if prompt is None:
        raise ValueError(f"Missing prompt template: {task_id}/{variant}")
    return prompt


def variants(task_id: str) -> tuple[str, ...]:
    """Keep one easy prompt when there is no distinct hard template."""
    easy = template(task_id, "easy")
    hard = _template(task_id, "hard")
    if hard is None or easy.split() == hard.split():
        return ("easy",)
    return ("easy", "hard")


def render(task_id: str, variant: str, inputs: dict) -> str:
    prompt = template(task_id, variant)
    # Replace the whole input JSON object so arrays/numbers retain their actual
    # types. The HTML template has human-readable placeholder strings.
    start = prompt.index("```json", prompt.index("## Inputs"))
    end = prompt.index("```", start + 7)
    prompt = (
        prompt[:start]
        + "```json\n"
        + json.dumps(inputs, indent=2, ensure_ascii=False)
        + "\n"
        + prompt[end:]
    )
    if "{{" in prompt:
        raise ValueError(f"Unfilled placeholder in {task_id}/{variant}")
    return prompt
