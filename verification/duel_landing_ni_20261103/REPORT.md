# Independent native duel confirmation and blocker 5 closure

**Maintained teacher strength passed in all three validation formats.** The repaired teacher's independent duel result was −0.2083 percentage points against the ambush-compatible original Astra strategy, with a 95% interval of [−2.8125, +1.9271]. The lower endpoint exceeds the predeclared −5 point margin. FFA and team use their earlier passing measurements on the verified identical four-player path.

| Validation format | Evidence for this candidate | Games | Blocks / families | Normalized difference (pp) | 95% interval (pp) |
| --- | --- | ---: | ---: | ---: | --- |
| Duel, Hamlets | New, source `31e6f2a` | 1,920 | 960 / 15 | −0.2083 | [−2.8125, +1.9271] |
| FFA, Loris River | Reused, source `97d7d9d` | 1,200 | 300 / 15 | +1.0556 | [−4.3611, +6.7917] |
| Team, Loris River | Reused, source `97d7d9d` | 1,440 | 180 / 15 | 0.0000 | [−3.4028, +2.9861] |

The score is the official candidate-minus-control difference, normalized by three for duel and team. FFA uses rank points divided by three. Team equally weights its two contexts. The prior baseline-partner estimate was +0.5556 pp [−5.5556, +6.2500], and self-team −0.5556 pp [−1.9444, +0.5556]. The original 4,560-game panel remains recorded as failed on its then-current duel branch. [Previous endpoint and raw records](../teacher_noninferiority_20261103/REPORT.md) · [Prospective duel protocol](protocol_source.txt)

## New duel endpoint

Eight Ubuntu workers completed all 1,920 scheduled games without faults. Each job ID occurs once in each of the schedule, append log and results file. The ID sets match, the two result records are identical per ID and the actual seeds, seats and faction assignments match the schedule. There are 960 complete two-seat blocks, with 64 distinct paired seeds in each of 15 families. These seeds do not occur in the prior R3 schedules. There are zero missing blocks and zero candidate truncations.

The candidate won 877 games and lost 881. These 1,758 games ended by last leader. All 162 draws were official 30-turn adjudications. The raw mean official scores on the 3/1/0 scale were 1.4546875 for the candidate and 1.4609375 for the control, a difference of −0.00625. The unchanged family-cluster bootstrap used 5,000 resamples, seed 19, and returned raw endpoints [−0.084375, +0.0578125]. Dividing by three gives the normalized duel interval above. The original superiority comparison is `inconclusive`. The user-selected maintained-strength criterion is `passed`. [Unrounded runner summary](summary.json)

Preparation froze the schedule on 2026-11-03 at 18:51:40 Asia/Shanghai with a six-hour deadline of 00:51:40 the next day. The single execution started at 18:52:19 and reached its endpoint at 19:32:00 the same evening (2,380.57 seconds). The broker measured 2,380.12 seconds, or 2,904.06 games per hour. The run exited 0. Interim observations covered process identity, completed counts and faults only. [Plan](plan.json) · [Run start](execution.json)

## Identity and four-player reuse

The prelaunch scope review compares source `31e6f2a2c0196539636e3cca4578e6d9c5bd1658` against `97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3`. The only change outside documentation, tests and verification is `learning/teachers/gpt6astra/lua/duel.lua`. The referee, evaluation, shared observers, faction and map profiles and SDK are identical. The installed game's `share/wesnoth` tree contained 21,703 entries, with no observed ctime or mtime after the reference panel started. All 15 common input identities matched, including the native executable, shim and rules. [Scope review before the first game](scope-review.json) · [Frozen identities and individual hashes](identities.json)

The actual candidate zip has eight members. Only `astra_adapted/lua/duel.lua` differs from the previous staged candidate. The dispatcher selects `four.lua` for both FFA and team, and its shared value module is identical. All seven members of the compatible control package match the previous one byte for byte after unpacking. The underlying frozen parent SHA256 is `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`. The reference summary SHA256 is `8d56d7df50d9b53d83e824ddcb8b5d155351818d4f7c1966cd6be129f0e7d44d`. These checks establish applicability of the earlier two four-player comparisons to this candidate.

| Frozen or recorded artifact | SHA256 |
| --- | --- |
| Git source tar | `ba5649a61326c8cc115f3c9ef98fbc8f38f93c8beaf90fd1b7b17c4b539f4e3d` |
| Teacher source | `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5` |
| Actual staged candidate zip | `472619df1b8d62f08ef3bce1025d1c2575c68ac96d22c46376823718816eb9fd` |
| Actual staged compatible control zip | `ad4115783ba1a38871f5ffcbbbc5a1fb0a202e112d4c2a48fa7b09c462354c67` |
| Plan | `6c4244b264953452238c4894bb683aac33bcc1ecd0450055cc2971c7278d12e3` |
| Identities | `7cacb40f1437a5fd888bedaf1f47503d440c79f655daeab49fd25f8471e2c598` |
| Schedule | `b0a54c2b0e24fde606c1523b6d1c6d46be486a01b7878d9908aa68ece794d602` |
| Append log | `508d382a44691beec2cf15e5115328105b09ed55390f8d672fbc6a159edf2593` |
| Results | `601b41cd2187b9b45b2fa4c92486f8607f4b27e7569f7605643159f07c18ad38` |
| Summary | `c1d27029265674a5f1a66b91f8586f4e23e0ffbfae869471d13f5916a4f597d4` |

## Reproduction and archives

The source was shipped as a git archive containing all tracked root entries except `verification/`, `runs/` and `delivery/`. Local and Ubuntu archive hashes matched before extraction. The fresh directory used the existing read-only combat-filtered rules and validation map directories. The shim was built there with `gcc -shared -fPIC -O2 vendor/arena/entropy.c -o .runtime/entropy.so -ldl`. Numerical libraries used one thread, SDL used dummy audio and video, and `PYTHONPATH` included the accepted v6 extension, the fresh root and `vendor/arena`. From that root the two commands, both exit 0, were:

```sh
root=/home/tongshu/acceptance/duel_landing_ni_20261103
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py prepare \
  --root "$root" --output "$root/panel" --source-commit 31e6f2a2c0196539636e3cca4578e6d9c5bd1658 \
  --source-archive /home/tongshu/acceptance/duel-landing-ni-20261103.tar \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --duel-noninferiority --reuse-panel /home/tongshu/acceptance/teacher_noninferiority_20261103/panel
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py run --output "$root/panel"
```

The Git bundle (826,549 bytes, SHA256 `b3f8fa053f58a7f19a8b824f9955f895307a97a28129269a6ac60271d58d37b9`) contains every scheduled job and raw outcome, both staged packages, plan and identities, throughput, run log, exit code and summary. The protocol is an exact copy of the one in the shipped commit. [Panel records](panel-records.tar.gz)

The full archive (92,660,747 bytes, SHA256 `9ed31fafba614ba55d497a8203520faa013d1f88ff666fc303c3e67c59394859`) contains all 1,920 native replays and their event, JSON and log files. It matches the terminal Ubuntu directory in a tar comparison. Ubuntu and Windows copies have the same size and hash. The Ubuntu copy is `/home/tongshu/acceptance/duel_landing_ni_20261103-panel.tar.gz`. The workspace copy is `completed/duel_landing_ni_20261103-panel.tar.gz` beside this report. The original Ubuntu directory is retained.

## Acceptance scope

R3 and blocker 5 close on supported combat transfer and maintained native **teacher** strength on the specified validation maps, comparator and 30-turn contract. The fixed-board evidence covers public probability/seed handling, supported weapon declarations and advancement, per-unit immunity, legal teacher choices, native ambush and surviving slow valuation. The b0025 native rank reversal and independent Lite red/green regression verify the only production change since the reference panel. Full native semantic equivalence and trained-policy strength remain outside this acceptance. Ordinary BC, final evaluation of selected weights and the complete training loop retain their own gates. [Repair evidence](../duel_slow_landing_20261103/REPORT.md) · [Blocker 5 scope and combat evidence](../../docs/blockers_temp.md#5-completed--supported-combat-transfer-and-maintained-native-teacher-strength)
