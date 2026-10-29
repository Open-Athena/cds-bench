"""Read the published definitions and exact prompt templates without editing them."""

import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "index.html").read_text()
SPEC_SHA256 = hashlib.sha256(SPEC.encode()).hexdigest()
DATA = json.loads(
    re.search(r'<script type="application/json" id="task-data">(.*?)</script>', SPEC, re.S)[1]
)
TASKS = {
    t.get("task_type", t.get("composition_type")): t for t in DATA["tasks"] + DATA["compositions"]
}


def template(task_id: str, variant: str) -> str:
    prefix = "composition" if task_id.startswith(("pipeline.", "joint.")) else "task"
    element = f"{prefix}-{task_id}-{variant}"
    match = re.search(
        r'<pre[^>]*id="' + re.escape(element) + r'"[^>]*><code>(.*?)</code></pre>', SPEC, re.S
    )
    if match is None:
        raise ValueError(f"Missing prompt template: {element}")
    return html.unescape(match[1]).strip()


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
