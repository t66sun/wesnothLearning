# R3 non-inferiority panel startup — 2026-11-03

The user selected the maintained-strength fallback after two completed scoring
repair rounds and approved a margin of 0.05 on normalized official score.
The committed protocol predates the first game. This record proves preparation
and a live start only; it contains no statistical acceptance result.

## Frozen source and inputs

- Shipped source: `97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3`.
- Git archive SHA256, matching locally and on Ubuntu:
  `20d1c2e2120375f3ddaa8a83c347f33e17cbb682c4a4220c8a4cea9f7243f8bc`.
- Archive: `/home/tongshu/acceptance/teacher-noninferiority-20261103.tar`.
- Fresh root: `/home/tongshu/acceptance/teacher_noninferiority_20261103`.
- Plan SHA256: `92da1c868b4bf11524a7071ce233e6c53438a80560b6329ae087a23ff03e3abc`.
- Schedule SHA256: `1343852a01d6ea62152aae6f38ae4cb08fef15d422c286ee38a1e7d939cf8987`.
- Identities SHA256: `110559e5814723a8130600ba76419fa62d177b3b1fcf1de98f7973874a594f65`.
- Candidate teacher SHA256 remains
  `ad75d870ce68fa6b489ad922fd8bb3059e29bbe7626f296e74d2b6fad828c7d4`.
- Historical parent archive remains
  `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`.
- Staged candidate package SHA256:
  `773047bffe6a29188cbfbd64b3f37e6906cb4f7fce3ee40b49f73e0d193a9a9f`.
- Ambush-compatible control package SHA256:
  `a6beba9667c2aa5ac777b98b6c2074312779e1adb92c7c870393d22206ba05ec`.

`identities.json` contains the executable, shim, rules, helper and per-file
control patch hashes. `plan.json` and `execution.json` are byte-identical copies
from Ubuntu. `protocol_source.txt` preserves the committed Markdown protocol
verbatim; its original relative links refer to the source repository. The
readable source protocol is [at the shipped commit](https://github.com/t66sun/wesnothLearning/blob/97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3/docs/r3_noninferiority_temp.md).

## Preparation and launch

The source archive uses all tracked root entries except historical
`verification/`, `runs/` and `delivery/`. From PowerShell:

```powershell
$sourceCommit = '97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3'
$sourceMembers = @(git ls-tree --name-only $sourceCommit |
    Where-Object { $_ -notin @('verification','runs','delivery') })
git archive --format=tar --output=tmp/teacher-noninferiority-20261103.tar $sourceCommit -- $sourceMembers
```

After transfer completion and matching SHA256, extract into the fresh root,
link the existing read-only combat-filtered rules and historical map directory,
and run `gcc -shared -fPIC -O2 vendor/arena/entropy.c -o .runtime/entropy.so -ldl`.
The shim matches the accepted SHA256
`f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`.

From that root, using `/home/tongshu/venv/bin/python`, single-threaded numerical
libraries, the accepted extension path and dummy SDL video/audio drivers:

```sh
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py prepare \
  --noninferiority \
  --source-archive /home/tongshu/acceptance/teacher-noninferiority-20261103.tar \
  --source-commit 97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3 \
  --root /home/tongshu/acceptance/teacher_noninferiority_20261103 \
  --output /home/tongshu/acceptance/teacher_noninferiority_20261103/panel \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py run \
  --output /home/tongshu/acceptance/teacher_noninferiority_20261103/panel
```

Preparation exits 0. The run command redirects output to `panel/run.log`; its
shell records the eventual exit code in `panel/run.exit`. There was one launch,
without retry. Preparation time is 07:25:35 and run start is 07:26:48, both
Asia/Shanghai on 2026-11-03. The fixed deadline is 13:25:35 that day.

## Observed preflight and live state

Before launch, the frozen schedule contains 4560 unique job IDs, with zero game
seed overlap with the previous panel. Counts are 1920 duel / 1200 FFA / 1440
team games, 960/300/180 blocks, and 15 scenario families per format. Team contexts
have 720 jobs each. Every map is in validation and every turn limit is 30.

At 92.05 seconds after launch, `/proc/493190` exists with the expected Python
command and source working directory. Its job log contains 43 complete jobs and
zero fault games. No interim score, win/rank difference or confidence interval
was inspected. This initial observation is immutable, not a live progress file.

The helper's six Ubuntu checks and reporter's eight checks (three affected
checks rerun after review; five reused) are separate evidence under
`verification/teacher_control_compatibility_20261103/`,
`verification/teacher_ni_reporter_20261103/` and
`verification/teacher_ni_inconclusive_20261103/`. No collection, training or
Windows test ran. Final acceptance still requires the complete frozen panel
and all three format-level non-inferiority checks.
