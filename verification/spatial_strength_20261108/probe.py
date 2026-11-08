"""Score the two original public witness pairs with the frozen #269 wall actors."""

import argparse
import json
from pathlib import Path
import runpy

import torch

import _engine_lite
from learning.common import ROOT, sha256
from learning.export import load_model
from learning.model import batch


PAIRS = ('resampling_connectivity', 'pooling_location')
SEEDS = (202611071, 202611072, 202611073)


def public_inputs(fixture_path, arm):
    fixtures = runpy.run_path(fixture_path.with_name('fixtures.py'))
    recorded = json.loads(fixture_path.read_text(encoding='utf-8'))
    captured = {}
    for name in PAIRS:
        rows = []
        for label, spec in zip(('left', 'right'), fixtures['pairs']()[name], strict=True):
            original = recorded['spatial'][name][label]
            assert fixtures['public_spec'](spec) == original['spec']
            assert fixtures['rules']() == recorded['synthetic_rules']
            _, decision = fixtures['capture'](spec)
            row = fixtures['actor_row'](decision)
            assert len(row['candidates']) == 7
            assert {k: v for k, v in row.items() if k != 'spatial'} == {
                k: v for k, v in original['actor'].items() if k != 'spatial'
            }
            assert row['spatial']['entities'] == original['actor']['spatial']['entities']
            if arm == 'base':
                assert row == original['actor']
            else:
                assert row['spatial']['width'] == spec['width']
                assert row['spatial']['height'] == spec['height']
            rows.append(row)
        assert rows[0]['candidates'] == rows[1]['candidates']
        expect_board_change = arm == 'c' or name == 'pooling_location'
        assert (rows[0]['spatial']['board'] != rows[1]['spatial']['board']) == expect_board_change
        captured[name] = rows
    return captured


@torch.inference_mode()
def measure(model, rows):
    logits = torch.stack([model(*batch([row], dtype=torch.float64))[0][0] for row in rows])
    assert torch.isfinite(logits).all()
    probabilities = logits.softmax(-1)
    log_probabilities = logits.log_softmax(-1)
    candidates = [{k: row[k] for k in ('kind', 'type', 'x', 'y') if k in row}
                  for row in rows[0]['candidates']]
    ghost = [i for i, candidate in enumerate(candidates) if candidate.get('type') == 'Ghost']
    fighter = [i for i, candidate in enumerate(candidates) if candidate.get('type') == 'Fighter']
    assert len(ghost) == len(fighter) == 3
    ghost_log_odds = logits[:, ghost].logsumexp(-1) - logits[:, fighter].logsumexp(-1)
    return dict(
        candidates=candidates,
        logits=logits.tolist(),
        probabilities=probabilities.tolist(),
        top_choice=logits.argmax(-1).tolist(),
        max_abs_log_prob_change=float((log_probabilities[1] - log_probabilities[0]).abs().max()),
        total_variation=float((probabilities[1] - probabilities[0]).abs().sum() / 2),
        ghost_vs_fighter_log_odds=ghost_log_odds.tolist(),
        ghost_vs_fighter_log_odds_change=float(ghost_log_odds[1] - ghost_log_odds[0]),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('arm', choices=('base', 'c'))
    args = parser.parse_args()
    launch = json.loads((args.run/'launch-manifest.json').read_text())
    contract = launch['contracts'][args.arm]
    assert ROOT == Path(contract['source'])
    assert (ROOT.parent/'SOURCE_COMMIT').read_text().strip() == contract['commit']
    assert Path(_engine_lite.__file__) == Path(contract['extension'])
    assert sha256(Path(_engine_lite.__file__)) == contract['extension_sha256']
    fixture_path = ROOT/'verification/representation_information_20261106/paired_fixtures.json'
    rows = public_inputs(fixture_path, args.arm)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    seeds = {}
    for seed in SEEDS:
        ledger = args.run/'experiment'/f'{args.arm}-{seed}-ledger.json'
        endpoint = json.loads(ledger.read_text())['roles']['wall']
        checkpoint = Path(endpoint['path'])
        assert sha256(checkpoint) == endpoint['checkpoint_sha256']
        model, _ = load_model(checkpoint, 'duel')
        model = model.double().eval()
        seeds[seed] = dict(checkpoint=endpoint, pairs={
            name: measure(model, pair) for name, pair in rows.items()
        })
    print(json.dumps(dict(
        arm=args.arm, source_commit=contract['commit'], extension_sha256=contract['extension_sha256'],
        fixture_sha256=sha256(fixture_path), precision='float64', torch=torch.__version__, seeds=seeds,
    ), indent=2))


if __name__ == '__main__':
    main()
