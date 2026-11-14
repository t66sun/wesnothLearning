"""Measure #326 from the frozen v38 BC validation trajectories."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import time

import torch

from learning.common import read_json, sha256
from learning.coverage import FIELDS, matching
from learning.data import record_split
from learning.export import load_model
from learning.model import batch
from learning.sequences import read_raw_shards
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.ppo_batch_comparison_20261107.driver import bc_endpoint, worker_identity
from verification.ppo_batch_comparison_20261107.panels import INPUTS
from verification.ppo_terminal_return_20261108.driver import PARENT, RULES

COMBAT = ('attack', 'move_attack')
CASE = Path(__file__).resolve().parent


def classify(candidates, selected, intent):
    picked = candidates[selected]
    if picked['kind'] not in COMBAT:
        return 'greedy_noncombat', []
    if intent['kind'] not in COMBAT:
        return 'astra_noncombat', []
    index = matching(candidates, intent)
    if index < 0:
        return 'absent', []
    if index == selected:
        return 'same', []

    def coordinates(action):
        origin = action['x'], action['y']
        target = (action['ex'], action['ey']) if action['kind'] == 'move_attack' else (action['tx'], action['ty'])
        landing = (action['tx'], action['ty']) if action['kind'] == 'move_attack' else origin
        return dict(actor=origin, target=target, landing=landing, weapon=action['weapon'])

    before, after = coordinates(picked), coordinates(intent)
    return 'different', [key for key in before if before[key] != after[key]]


def audit(output, source_commit, archive):
    import _engine_lite
    from learning.common import ROOT

    started = time.monotonic()
    torch.set_num_threads(1)
    extension = Path(_engine_lite.__file__).resolve()
    worker_identity(dict(source=str(ROOT), commit=source_commit, extension=str(extension),
                         extension_sha256='56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4'))
    endpoint = bc_endpoint(PARENT)['endpoint']
    if (any(endpoint[key] != value for key, value in INPUTS['base_bc'].items())
            or sha256(RULES/'rules.json') != INPUTS['rules_sha256']):
        raise ValueError('v38 or rules do not match the qualified endpoint')
    path = PARENT/'duel/last_bc.pt'
    model, state = load_model(path, 'duel')
    model = model.double().eval()
    shards = {str(Path(path).resolve()) for path in state['runner']['teacher_shards']}
    replies = {}
    with (PARENT/'duel/jobs.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            reply = json.loads(line)
            if reply['id'].startswith('teacher-'):
                if reply['id'] in replies:
                    raise ValueError(f"duplicate teacher reply {reply['id']}")
                replies[reply['id']] = reply
    counts, changes = Counter(), Counter()
    breakdown = {key: defaultdict(Counter) for key in ('map', 'faction', 'game', 'greedy_kind')}
    witnesses, matched_shards, changed_boards, changed_games = [], set(), set(), set()
    validation_inputs = []
    inspected = Counter()
    for schedule in sorted((PARENT/'duel/schedules').glob('bc-batch-*.json')):
        for job in read_json(schedule):
            shard = str(Path(job['shard']).resolve())
            if shard not in shards:
                continue
            if shard in matched_shards:
                raise ValueError(f'duplicate teacher schedule for {shard}')
            matched_shards.add(shard)
            partition = record_split(job)
            inspected[partition] += 1
            if partition != 'validation':
                continue
            reply = replies[job['id']]
            if (reply['status'] != 'complete' or not reply['training_eligible']
                    or reply['result']['faults'] or not reply['result']['task_terminal']):
                raise ValueError(f"incomplete validation game {job['id']}")
            physical = board_digest(job['map_override'])
            rows = read_raw_shards([shard], 'duel')
            if len(rows) != reply['training_shard']['raw_records']:
                raise ValueError(f"incomplete raw trajectory {job['id']}")
            for start in range(0, len(rows), 32):
                chunk = rows[start:start + 32]
                with torch.inference_mode():
                    logits, _ = model(*batch(chunk, dtype=torch.float64, history_cache={}))
                choices = logits.argmax(dim=-1).tolist()
                for row, selected in zip(chunk, choices):
                    if (record_split(row) != partition or row['scenario_family'] != job['scenario_family']
                            or row['source'] != 'astra' or row['task_id'] != INPUTS['task_id']):
                        raise ValueError(f"unexpected trajectory provenance {job['id']}")
                    candidates, intent = row['candidates'], row['intent']
                    picked = candidates[selected]
                    outcome, differences = classify(candidates, selected, intent)
                    counts[outcome] += 1
                    for group, label in (('map', job['meta']['map']), ('faction', job['factions'][row['side']-1]),
                                         ('game', job['id']), ('greedy_kind', picked['kind'])):
                        breakdown[group][label][outcome] += 1
                    if outcome == 'different':
                        changes.update(differences)
                        changed_boards.add(physical)
                        changed_games.add(job['id'])
                        if len(witnesses) < 12 and job['id'] not in {w['game'] for w in witnesses}:
                            witnesses.append(dict(game=job['id'], turn=row['turn'], decision=row['decision'],
                                                  side=row['side'], changes=differences, choices=[
                                                      {key: action[key] for key in ('kind', *FIELDS[action['kind']])}
                                                      for action in (picked, intent)]))
            validation_inputs.append(dict(game=job['id'], shard_sha256=sha256(shard),
                                          board=physical, decisions=len(rows)))
    if matched_shards != shards:
        raise ValueError('teacher shards lack matching schedule records')
    decisions = sum(counts.values())
    combat = decisions - counts['greedy_noncombat']
    rate = counts['different'] / combat if combat else 0
    passed = rate >= .05 and len(changed_games) >= 12 and len(changed_boards) >= 2
    report = dict(source_commit=source_commit, source_archive_sha256=sha256(archive),
                  endpoint=endpoint, extension_sha256=sha256(extension), rules_sha256=INPUTS['rules_sha256'],
                  astra=INPUTS['astra'], inspected_teacher_games=inspected, validation_inputs=validation_inputs,
                  decisions=decisions, combat=combat, counts=counts, changes=changes, breakdown=breakdown,
                  changed_boards=sorted(changed_boards), changed_games=len(changed_games), rate=rate,
                  passed=passed, seconds=time.monotonic()-started, witnesses=witnesses)
    write_new(output, report)
    print(f'{counts["different"]}/{combat} ({rate:.2%}), {len(changed_games)} games, '
          f'{len(changed_boards)} boards, gate passed={passed}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('commit')
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    audit(args.output, args.commit, args.archive)
