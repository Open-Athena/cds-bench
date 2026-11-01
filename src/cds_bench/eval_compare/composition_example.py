"""Worked composition diagram from one unchanged evaluation instance."""

import base64
import hashlib
import html
import json
import os
import re

from cds_bench.catalog import ROOT, TASKS
from cds_bench import solve

TASK = 'pipeline.variant_peptides'
INSTANCE = TASK + '/03'
SPEC = 'https://openathena.ai/cds-bench/'


def prepare(cases, summary):
    case = cases[INSTANCE, 'easy']
    inputs = json.loads(case['inputs_json'])
    original = inputs['cds']
    edited = solve.edit(original, inputs['edits'])
    proteins = [solve.translate(s) for s in [original, edited]]
    peptides = [[p['peptide'] for p in solve.digest(protein)] for protein in proteins]
    answer = {'lost': sorted(set(peptides[0]) - set(peptides[1])),
              'gained': sorted(set(peptides[1]) - set(peptides[0]))}
    assert answer == json.loads(case['answer'])
    assert TASKS[TASK]['steps'] == ['variant.apply', 'cds.translate', 'protein.trypsin_digest']
    # Independently check the displayed instance, coordinates and digestion.
    assert inputs['edits'] == [{'replace': [10, 12, 'GCA']}]
    assert original[9:12] == 'CGG' and edited == original[:9] + 'GCA' + original[12:]
    assert proteins == ['MVGRVSQTALVGDVLIRILLAD', 'MVGAVSQTALVGDVLIRILLAD']
    assert [re.split(r'(?<=[KR])(?!P)', p) for p in proteins] == peptides
    family = next(r for r in summary['easy_family_comparison']['comparisons']
                  if r['family'] == 'composition' and r['condition'] == 'easy-tools')
    task = {m: {k: summary['by_task'][TASK][m]['easy-tools'][k] for k in ['correct', 'attempted']}
            for m in ['deepinfra', 'snowball-v01']}
    return {'instance_id': INSTANCE, 'task_id': TASK, 'title': TASKS[TASK]['title'],
            'inputs': inputs, 'edited_cds': edited, 'proteins': proteins,
            'digests': peptides, 'answer': answer, 'family_metrics': family, 'task_metrics': task,
            'prompt_sha256': hashlib.sha256(case['prompt'].encode()).hexdigest()}


def plot(output, data):
    cache = ROOT / 'build/eval-comparison-cache'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache / 'matplotlib'))
    os.environ.setdefault('XDG_CACHE_HOME', str(cache))
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Rectangle

    ink, muted, line = '#25313c', '#64727e', '#ced7df'
    dna, protein = '#205d89', '#745e88'
    lost, gained = '#a44849', '#337457'
    with mpl.rc_context({'svg.fonttype': 'none', 'font.family': 'DejaVu Sans'}):
        fig, ax = plt.subplots(figsize=(10.2, 6.55), dpi=180)
        fig.patch.set_facecolor('white')
        ax.set(xlim=(0, 1), ylim=(0, 1))
        ax.axis('off')
        fig.subplots_adjust(left=.015, right=.985, bottom=.015, top=.985)

        def text(x, y, s, size=11, color=ink, weight='normal', ha='left', mono=False, va='center'):
            return ax.text(x, y, s, fontsize=size, color=color, weight=weight, ha=ha, va=va,
                           family='DejaVu Sans Mono' if mono else 'DejaVu Sans', transform=ax.transAxes)

        def box(x, y, w, h, fill='white', border=line):
            ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=border, lw=.8))

        def arrow(x1, y1, x2, y2):
            ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>',
                                        mutation_scale=12, color=muted, linewidth=1))

        def sequence(x, y, s, marked=None, color=protein, size=13):
            # Exact monospace character positioning keeps residue highlights aligned.
            width = size * .602 / (fig.get_figwidth() * 72 * .97)
            start = x - len(s) * width / 2
            for i, char in enumerate(s):
                special = marked is not None and i == marked
                if special:
                    box(start + i*width - .002, y-.017, width+.004, .034, '#fff0dc', '#e4bf86')
                text(start+i*width, y, char, size, color, weight='bold' if special else 'normal', mono=True)

        text(.035, .955, 'From DNA edits to changed peptide readouts', 17, weight='bold')
        text(.035, .92, INSTANCE + ' · worked evaluation example', 10, muted)

        box(.035, .795, .93, .092, '#f5f8fb')
        text(.055, .865, 'INPUT: CODING DNA + EDIT', 9, dna, 'bold')
        codons = [data['inputs']['cds'][i:i+3] for i in range(0, len(data['inputs']['cds']), 3)]
        text(.5, .831, ' '.join(codons), 11.2, dna, ha='center', mono=True)
        text(.5, .775, '1. Apply DNA edit · variant.apply', 10, muted, ha='center')
        arrow(.255, .789, .255, .734)
        arrow(.745, .789, .745, .734)

        for x, title, detail in [(.04, 'Original CDS', 'Keep the supplied sequence'),
                                 (.53, 'Edited CDS', 'Bases 10–12: CGG → GCA')]:
            box(x, .655, .43, .075, '#f5f8fb')
            text(x+.215, .704, title, 11, dna, 'bold', ha='center')
            text(x+.215, .675, detail, 10, dna, ha='center')

        text(.5, .615, '2. Translate both CDSs · cds.translate', 10, muted, ha='center')
        for x in [.255, .745]:
            arrow(x, .65, x, .575)
        for x, p in zip([.04, .53], data['proteins']):
            box(x, .485, .43, .09, '#f6f2f8')
            sequence(x+.215, .54, p, marked=3)
            text(x+.215, .508, 'Residue 4: ' + p[3], 9, muted, ha='center')

        text(.5, .445, '3. Digest both proteins · protein.trypsin_digest', 10, muted, ha='center')
        for x in [.255, .745]:
            arrow(x, .48, x, .405)
        for x in [.04, .53]:
            box(x, .292, .43, .112)
        for x, fragments in zip([.255, .745], data['digests']):
            sequence(x, .367, ' | '.join(fragments), color=protein, size=11.7)
            text(x, .321, 'ILLAD is shared; omit it from the answer', 9, muted, ha='center')
        text(.5, .265, 'R4 → A removes a trypsin cut, merging two peptides.', 10.5, ink, ha='center')
        text(.5, .231, '4. Compare peptide sets: original-only = lost; edited-only = gained', 10, muted, ha='center')
        arrow(.255, .29, .255, .197)
        arrow(.745, .29, .745, .197)

        box(.04, .065, .43, .13, '#fbf1f1', '#dfbfc0')
        box(.53, .065, .43, .13, '#eef6f0', '#bcd4c5')
        text(.06, .166, 'LOST', 10, lost, 'bold')
        text(.06, .128, data['answer']['lost'][0], 12, lost, mono=True)
        text(.06, .091, data['answer']['lost'][1], 12, lost, mono=True)
        text(.55, .166, 'GAINED', 10, gained, 'bold')
        text(.55, .118, data['answer']['gained'][0], 12, gained, mono=True)
        text(.5, .03, 'Trypsin rule: cut after K or R, except before P. Stops are omitted from protein sequences.',
             9, muted, ha='center')
        for suffix in ['svg', 'png']:
            fig.savefig(output / ('composition-example.' + suffix), facecolor='white',
                        metadata={'Description': 'DNA edit, translation, trypsin digestion and peptide-set comparison.'}
                        if suffix == 'svg' else None)
        plt.close(fig)


def export(output, cases, summary):
    data = prepare(cases, summary)
    (output / 'composition-example.json').write_text(json.dumps(data, indent=2) + '\n')
    plot(output, data)
    return data


def description(data):
    n, s = [data['task_metrics'][m] for m in ['deepinfra', 'snowball-v01']]
    return (
        f"For the illustrated task on Easy/Python, Nemotron scores {n['correct']/n['attempted']:.1%} "
        f"({n['correct']}/{n['attempted']}) versus {s['correct']/s['attempted']:.1%} "
        f"({s['correct']}/{s['attempted']}) for Snowball."
    )


EXPLANATION = (
    'In this task, the model applies a DNA edit, translates the original and edited CDSs, '
    'digests both proteins with trypsin, and reports the peptides lost or gained. '
    'In the illustrated example, R4 → A removes a cleavage site and merges two peptides.'
)


def markdown(data, base, image_base):
    image_hash = hashlib.sha256((image_base / 'composition-example.png').read_bytes()).hexdigest()[:12]
    raw = base.replace('https://github.com/', 'https://raw.githubusercontent.com/').replace('/blob/', '/refs/heads/')
    components = ' → '.join(f'[{task}]({SPEC}#task-{task})' for task in TASKS[TASK]['steps'])
    return (f'[Example composition task: {data["title"]}]({base}/report.html#task-{TASK}). ' + EXPLANATION + '\n\n'
            'Components: ' + components + '.\n\n'
            f'![Worked composition task: DNA edit, translation, digestion and peptide comparison]({raw}/composition-example.png?v={image_hash})\n\n'
            f'[PNG]({raw}/composition-example.png?v={image_hash}) · [SVG]({base}/composition-example.svg)\n\n' + description(data))


def html_section(output, data):
    esc = html.escape
    png = base64.b64encode((output / 'composition-example.png').read_bytes()).decode()
    components = ' → '.join(f'<a href="{SPEC}#task-{task}">{esc(task)}</a>' for task in TASKS[TASK]['steps'])
    return ('<h4 id="composition-example">Example composition task: <a href="#task-' + TASK + '">' + esc(data['title']) + '</a></h4>'
            '<p>' + esc(EXPLANATION) + '</p><p>Components: ' + components + '.</p><figure style="margin:16px 0">'
            '<img alt="DNA edit, translation, trypsin digestion and peptide-set comparison" src="data:image/png;base64,' + png + '">'
            '<figcaption><a href="composition-example.svg">SVG</a> · <a href="composition-example.png">PNG</a></figcaption></figure>'
            '<p>' + esc(description(data)) + '</p>')
