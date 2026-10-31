"""Three task-level radar panels from saved metrics, with a shared linked key."""

import html
import json
import math
import xml.etree.ElementTree as ET
from statistics import mean

from cds_bench.catalog import TASKS


FAMILIES = {
    "sequence": ("Sequence operations", "#4477aa"),
    "variation": ("Variant effects", "#ee6677"),
    "measure": ("Sequence statistics", "#228833"),
    "protein": ("Protein operations", "#b49b30"),
    "rna": ("RNA operations", "#55aacc"),
    "redesign": ("Synonymous design", "#aa3377"),
    "construct": ("Construct design", "#dd7733"),
    "assay": ("Assay design", "#009988"),
    "overlap": ("Overlapping frames", "#777777"),
    "composition": ("Composition tasks", "#332288"),
}
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"


def prepare(summary, models):
    tasks = []
    for task_id, task in TASKS.items():
        metrics = {}
        for model in models:
            conditions = summary["by_task"][task_id][model].values()
            correct = sum(r["correct"] for r in conditions)
            attempted = sum(r["attempted"] for r in conditions)
            metrics[model] = {"correct": correct, "attempted": attempted,
                              "accuracy": correct / attempted if attempted else None}
        values = [m["accuracy"] for m in metrics.values() if m["accuracy"] is not None]
        tasks.append({"task_id": task_id, "title": task["title"],
                      "family": task.get("family", "composition"), "models": metrics,
                      "mean_accuracy": mean(values) if values else None})
    groups = []
    rank = lambda value: -(value if value is not None else -1)
    for family, (name, color) in FAMILIES.items():
        members = sorted((t for t in tasks if t["family"] == family),
                         key=lambda t: (rank(t["mean_accuracy"]), t["task_id"]))
        if members:
            values = [t["mean_accuracy"] for t in members if t["mean_accuracy"] is not None]
            groups.append({"family": family, "name": name, "color": color,
                           "mean_accuracy": mean(values) if values else None, "tasks": members})
    groups.sort(key=lambda g: (rank(g["mean_accuracy"]), g["family"]))
    for index, group in enumerate(groups):
        group["code"] = chr(ord("A") + index)
        for number, task in enumerate(group["tasks"], 1):
            task["code"] = f'{group["code"]}{number:02}'
    assert sum(len(g["tasks"]) for g in groups) == len(TASKS) == 84
    return {
        "models": models,
        "score": "Correct / attempted across all retained conditions for each task; all failures count.",
        "ordering": "Descending mean task accuracy across models, first by group then within group; ties use family or task ID.",
        "group_average": "Unweighted mean of task means within each group.",
        "groups": groups,
    }


def plot(output, summary, models):
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Patch

    data = prepare(summary, models)
    groups = data["groups"]
    tasks = [t for group in groups for t in group["tasks"]]
    gap = 1.2
    unit = 2 * math.pi / (len(tasks) + gap * len(groups))
    cursor, angles = 0, []
    for group in groups:
        group["angle_start"] = cursor * unit
        for task in group["tasks"]:
            task["angle"] = (cursor + 0.5) * unit
            angles.append(task["angle"])
            cursor += 1
        group["angle_end"] = cursor * unit
        cursor += gap

    with mpl.rc_context({"svg.fonttype": "none", "svg.hashsalt": "cds-bench-task-radar"}):
        fig, axes = plt.subplots(1, 3, figsize=(18, 7.2), subplot_kw={"projection": "polar"})
        fig.subplots_adjust(left=0.015, right=0.985, bottom=0.18, top=0.88, wspace=0.11)
        for ax, (model, name) in zip(axes, models.items(), strict=True):
            ax.set_theta_zero_location("N")
            ax.set_theta_direction(-1)
            ax.set_ylim(0, 1.22)
            ax.set_xticks([])
            ax.set_yticks([0.25, 0.5, 0.75, 1], ["", "", "", ""])
            for radius in [0.25, 0.5, 0.75, 1]:
                ax.text(math.pi / 2, radius - 0.015, f"{radius:.0%}", ha="right", va="center",
                        fontsize=8, color="#64727e", zorder=6,
                        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 0.2})
            ax.grid(color="#dce2e7", linewidth=0.6)
            ax.spines["polar"].set_visible(False)
            ax.set_axisbelow(True)
            for group in groups:
                start, end = group["angle_start"], group["angle_end"]
                center, width = (start + end) / 2, end - start
                ax.bar(center, 1, width=width, bottom=0, color=group["color"], alpha=0.035, linewidth=0, zorder=0)
                ax.bar(center, 0.035, width=width, bottom=1.025, color=group["color"], linewidth=0, zorder=3)
                for angle in [start, end]:
                    ax.plot([angle, angle], [0, 1.06], color="#cbd3da", linewidth=0.6, zorder=0)
                for task in group["tasks"]:
                    angle = task["angle"]
                    ax.plot([angle, angle], [0, 1], color="#dce2e7", linewidth=0.3, zorder=0)
                    value = task["models"][model]["accuracy"]
                    if value is not None:
                        ax.scatter([angle], [value], s=10, color=group["color"], edgecolors="white", linewidths=0.25, zorder=5)
                    degrees = math.degrees(angle) % 360
                    rotation = 90 - degrees
                    if 180 < degrees < 360:
                        rotation += 180
                    label = ax.text(angle, 1.135, task["code"], fontsize=9, color="#334155",
                                    rotation=rotation, rotation_mode="anchor", ha="center", va="center")
                    label.set_gid(f'radar-label-{model}-{task["task_id"]}')
                    label.set_url(f'#task-{task["task_id"]}')
            values = [t["models"][model]["accuracy"] for t in tasks]
            contour = [v if v is not None else np.nan for v in values]
            ax.plot(angles + [angles[0] + 2 * math.pi], contour + contour[:1], color="#344554", linewidth=1.1, zorder=4)
            ax.fill(angles + [angles[0] + 2 * math.pi], contour + contour[:1], color="#344554", alpha=0.055, zorder=2)
            center = (ax.get_position().x0 + ax.get_position().x1) / 2
            fig.text(center, 0.967, name, ha="center", va="top", fontsize=13, color="#25313c")
            score = mean(v for v in values if v is not None)
            fig.text(center, 0.925, f"Mean task accuracy: {score:.1%}", ha="center", fontsize=10, color="#64727e")
        handles = [Patch(facecolor=g["color"], label=f'{g["code"]}  {g["name"]} ({g["mean_accuracy"]:.0%})') for g in groups]
        # Matplotlib fills legend columns; keep the displayed group order row-first.
        handles = [handles[i] for column in range(5) for i in range(column, len(handles), 5)]
        fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.045), ncol=5,
                   frameon=False, fontsize=9.5, handlelength=0.9, columnspacing=1.8)
        fig.text(0.5, 0.016, "84 tasks · all retained conditions pooled per task · same task order and 0–100% scale in every panel",
                 ha="center", fontsize=9, color="#64727e")
        fig.savefig(output / "task-radar.png", dpi=200, facecolor="white")
        fig.savefig(output / "task-radar.svg", metadata={"Date": None})
        plt.close(fig)

    # Keep actual text in the SVG, and make each compact label an accessible link.
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    tree = ET.parse(output / "task-radar.svg")
    root = tree.getroot()
    root.set("role", "group")
    root.set("aria-label", "Accuracy across all 84 tasks, with one radar panel per model and linked task codes")
    lookup = {t["task_id"]: t for t in tasks}
    for element in root.iter(f"{{{SVG}}}g"):
        identity = element.get("id", "")
        if not identity.startswith("radar-label-"):
            continue
        model, task_id = identity.removeprefix("radar-label-").split("-", 1)
        task = lookup[task_id]
        link = element.find(f"{{{SVG}}}a")
        score = task["models"][model]
        description = f'{task["code"]}: {task["title"]} ({task_id}). {models[model]}: {score["correct"]}/{score["attempted"]}.'
        link.set("href", f"report.html#task-{task_id}")
        link.set(f"{{{XLINK}}}href", f"report.html#task-{task_id}")
        link.set("target", "_self")
        link.set("aria-label", description)
        ET.SubElement(link, f"{{{SVG}}}title").text = description
    tree.write(output / "task-radar.svg", encoding="unicode")
    (output / "task-radar.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


def section(output, summary, models):
    data = prepare(summary, models)
    esc = html.escape
    svg = ((output / "task-radar.svg").read_text()
           .replace('<svg ', '<svg class="task-radar-svg" ', 1)
           .replace('href="report.html#task-', 'href="#task-'))
    parts = ['<h2 id="task-radar">All 84 tasks</h2>',
             '<p>Each spoke is one task. Its score pools all retained conditions: 40 attempts per model, or 20 for the five tasks without a hard variant. All failures count. Each model has the same task order and 0–100% scale.</p>',
             '<p>Groups are ordered from highest to lowest mean task accuracy across the three models; tasks use the same descending sort within each group. Every task has equal weight in the group average. Ties use the family or task ID.</p>',
             '<figure class="task-radar-figure"><div class="scroll">' + svg + '</div><figcaption>Colors mark task groups. Hover a code for the full name, ID and score; click it to open the existing task details. On a narrow screen, scroll horizontally to see all three panels.</figcaption></figure>',
             '<p><a href="task-radar.svg">SVG</a> · <a href="task-radar.png">PNG</a> · <a href="task-radar.json">Task order and scores</a></p>',
             '<details id="radar-task-key"><summary>Task key: all 84 codes, full names and IDs</summary>',
             '<div class="scroll"><table class="radar-key"><thead><tr><th>Code</th><th>Task</th><th>Mean accuracy</th></tr></thead>']
    for group in data["groups"]:
        parts.append(f'<tbody><tr class="radar-key-group"><th colspan="3"><span class="radar-swatch" style="background:{group["color"]}"></span>{group["code"]} · {esc(group["name"])} · {len(group["tasks"])} tasks · {group["mean_accuracy"]:.1%}</th></tr>')
        for task in group["tasks"]:
            parts.append(f'<tr><th scope="row">{task["code"]}</th><td><a href="#task-{task["task_id"]}">{esc(task["title"])}</a><small><code>{esc(task["task_id"])}</code></small></td><td>{task["mean_accuracy"]:.1%}</td></tr>')
        parts.append('</tbody>')
    parts.append('</table></div></details>')
    return ''.join(parts)
