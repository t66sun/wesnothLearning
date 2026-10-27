# R3 frozen-KL resume probe — 2026-10-27

Source: `f0646246887d805adc88897082a3a4e6e34a02e0`. Five one-decision synthetic games, two planned optimizer steps, existing deterministic PPO fixture/model. The second logical batch receives a deliberate frozen behavior-log-probability offset to force rejection; this is a fault-injection fixture, not a claim about the numerical KL of the historical run.

Command (Windows reference): `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/Scripts/python.exe verification/ppo_refactor_r3_probe_20261027/probe.py`. Exit 0; raw [local.log](local.log), [probe](probe.py).

First call commits one step/four decisions, then stops at KL 0.9007213115692139 (>0.02). Two calls with the same model, optimizer, rows and returned cursor each stop at exactly the same KL; cumulative updates stay one and committed decisions stay four. Both retries preserve the policy digest. Input content identity stays `1aceceec2fa9aa54b5e73d2678b1d29b614f339b58098cd375963009e2207d24`.

Conclusion: simply keeping KL-rejected work pending cannot guarantee subsequent optimization under fixed weights, reference probabilities and a deterministic pre-step gate. The user explicitly approved revising R3: account remaining work as `stopped_by_kl` and end that batch, while preserving pending/resume only for interruption/deadline. No gate or behavior probabilities change. This corrects the plan's guarantee; it does not prove the original KL threshold is optimal.

Ubuntu was not run for this diagnostic; R3 implementation acceptance is separate. No real game, collection or formal training occurred; existing recorded inputs/evidence were not modified.
