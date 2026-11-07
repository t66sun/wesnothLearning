"""Prove 4/8 launch and resume with collection blocked at the broker."""
from pathlib import Path
import time

import torch

from learning import coordinator
from learning.bc_anchor import weights_sha256
from learning.common import read_json
from verification.ppo_batch_contract_20261107.driver import resume_arm, start_arm


class NoCollection:
    def __init__(self, requests):
        self.requests = requests

    def get_nowait(self):
        request = self.requests.get_nowait()
        if request[1]:
            raise AssertionError('the dry run attempted to collect a game')
        return request


if __name__ == '__main__':
    broker = coordinator.broker

    def guarded_broker(processes, requests, replies, workers, directory):
        return broker(processes, NoCollection(requests), replies, workers, directory)

    coordinator.broker = guarded_broker
    previous = Path('/home/tongshu/acceptance/duel_comparison_20261106_43325b3/source/runs/duel_ppo_comparison_20261106')
    endpoint = read_json(previous / 'bc-endpoint.json')
    output = Path('runs/ppo_a2_startup_20261107').resolve()
    human = output / 'human-empty'
    human.mkdir(parents=True)
    for width in (4, 8):
        root = output / f'arm{width}'
        now = time.time()
        started = start_arm(root, previous / 'runs/bc', human, endpoint, seed=202611061,
                            rollout_games=width, admission=now - 1, deadline=now + 120)
        manifest = (root / 'manifest.json').read_bytes()
        budget_path = root / 'budget.json'
        budget = budget_path.read_bytes()
        assert read_json(root / 'manifest.json')['config']['rollout_games'] == width
        assert read_json(budget_path)['admission_deadline'] == now - 1
        assert read_json(budget_path)['hard_deadline'] == now + 120
        resumed = resume_arm(root)
        assert started['status'] == resumed['status'] == 'stage_complete', (started, resumed)
        assert (root / 'manifest.json').read_bytes() == manifest
        assert budget_path.read_bytes() == budget
        assert not (root / 'duel/jobs.jsonl').exists()
        assert not (root / 'scheduler.jsonl').exists()
        final = torch.load(root / 'duel/latest.pt', map_location='cpu', weights_only=False)
        assert final['runner']['batch'] == read_json(budget_path)['first_batch']
        assert final['runner']['phase'] == 'ppo'
        assert not final['runner']['pending_train']
        assert not final['optimizer']['state']
        assert weights_sha256(final['model']) == endpoint['weights_sha256']
        print(f"arm={width} first_batch={final['runner']['batch']} jobs=0 optimizer_states=0 "
              f"weights_sha256={endpoint['weights_sha256']} start_and_resume=stage_complete")
