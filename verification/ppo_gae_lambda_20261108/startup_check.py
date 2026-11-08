"""Open both branches from the qualified #227 BC, with game admission closed."""
import argparse
from pathlib import Path
import time
from unittest.mock import patch

import torch

from learning import coordinator
from learning.bc_anchor import weights_sha256
from learning.common import read_json
from verification.ppo_batch_contract_20261107 import driver
from verification.ppo_batch_contract_20261107.startup_check import NoCollection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comparison', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    endpoint = read_json(args.comparison/'bc-endpoint.json')
    parent = args.comparison/'runs/bc'
    human = args.output/'human-empty'
    human.mkdir(parents=True)
    original_broker = coordinator.broker
    configuration = driver.configuration

    def guard(processes, requests, replies, workers, directory):
        return original_broker(processes, NoCollection(requests), replies, workers, directory)

    with patch.object(coordinator, 'broker', guard):
        for lam in (.95, 1.):
            root = args.output/f'lambda-{lam}'
            now = time.time()
            with patch.object(driver, 'configuration',
                              lambda *args: configuration(*args) | dict(gae_lambda=lam)):
                started = driver.start_arm(root, parent, human, endpoint, seed=202611081,
                                           rollout_games=8, admission=now-1, deadline=now+120)
            files = ('manifest.json', 'budget.json', 'clock.json')
            frozen = [(root/name).read_bytes() for name in files]
            resumed = driver.resume_arm(root)
            assert started['status'] == resumed['status'] == 'stage_complete', (started, resumed)
            assert frozen == [(root/name).read_bytes() for name in files]
            assert read_json(root/'manifest.json')['config']['gae_lambda'] == lam
            assert read_json(root/'budget.json')['hard_deadline'] == now+120
            assert not (root/'duel/jobs.jsonl').exists()
            final = torch.load(root/'duel/latest.pt', map_location='cpu', weights_only=False)
            assert final['runner']['reward_controller']['config']['gae_lambda'] == lam
            assert not final['optimizer']['state'] and not final['runner']['pending_train']
            assert weights_sha256(final['model']) == endpoint['weights_sha256']
            print(f'lambda={lam} games=0 Adam_states=0 weights={endpoint["weights_sha256"]} '
                  'original_budget=retained start_and_resume=stage_complete', flush=True)


if __name__ == '__main__':
    main()
