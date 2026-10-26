"""Read downloaded JSON only; no model loading, games or parameter updates."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'delivery/lite_final_20261026_draft'


def main():
    inputs = {}
    for name in ('summary.json', 'manifest.json'):
        inputs[name] = hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest()
    summary = json.loads((PACKAGE / 'summary.json').read_text(encoding='utf-8'))
    formats = {}
    for fmt, result in summary['formats'].items():
        controls = {}
        for label, panel in result['controls'].items():
            values = [v for _, v in sorted(panel['block_differences'].items(),
                                          key=lambda item: int(item[0]))]
            period = next(k for k in range(1, len(values) + 1)
                          if all(v == values[i % k] for i, v in enumerate(values)))
            controls[label] = dict(blocks=panel['blocks'], missing=panel['missing_blocks'],
                                   faults=panel['fault_games'], score_period=period,
                                   distinct_scores=len(set(values)), first_period=values[:period],
                                   difference=panel['difference'], interval95=panel['interval95'])
        quality = result['bc_gate']['imitation']['formats'][fmt]
        formats[fmt] = dict(status=result['status'], selected_version=result['version'],
                            candidate_version=result['selection']['candidate_version'],
                            selection_reason=result['selection']['reason'],
                            selected_sha256=result['checkpoint_sha256'],
                            bc_samples=quality['samples'], bc_accuracy=quality['accuracy'],
                            bc_recruit=quality['kinds']['recruit'],
                            bc_gate_passed=result['bc_gate']['passed'], controls=controls)
    print(json.dumps(dict(scope='local existing JSON only; score repetition is not trajectory equality',
                          input_sha256=inputs, formats=formats), indent=2))


if __name__ == '__main__':
    main()
