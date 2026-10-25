# WesnothLearning

> Language: English | [中文](docs/README_zh.md)

Three independent models for Wesnoth 1.18.8: single combat `duel`, four-player free-for-all `ffa4` and team `team2v2`. Training uses Python/PyTorch with the native game and a Rust lite engine; the final artifact deploys as a pure Lua AI inside the native game.

## Documentation

- [Architecture, parameters and implemented/unimplemented items](docs/architecture.md): the single maintained architecture document, replacing the old PLAN.
- [Pending acceptance list](docs/TEST.md): minimal Ubuntu acceptance plans for implemented changes on the way to formal training.
- [Agent training operations guide](docs/instructions.md): taking over the environment, start/resume, maintenance, diagnosis and instruction-driven tuning.
- [Ubuntu 24.04 training bundle](docs/bundle.md): build and verify the extraction-ready archive, install it on a clean machine and start training.
- [Provenance and licensing](docs/THIRD_PARTY.md): third-party code, reference competitor packages and official component licenses.

The current pretraining collection target is **300** valid Astra teacher games for duel, **600** for FF4 and **400** for 2v2, **1300** in total, all on lite with 0 native anchors, at the default of **8 global workers**. These defaults passed restricted acceptance on Ubuntu; the earlier formal experiments have ended in failure and no new formal training is currently running.

The Rust rule core, spatial/relational/memory model, BC/PPO/DAgger, online reward control and pure Lua export are all implemented. New experiments use lite by default with the 587 units and 438 terrains of `data/rules/1.18.8-training`, gated at startup by the 158-unit six-faction training closure, with the real Astra teacher wired into all three formats. Boundaries for full campaign behavior, full-pipeline performance and formal training strength are in the architecture document.

The current implementation is schema 5 / candidate v3, adding the public tactical inputs needed for four-player BC; Ubuntu has passed the restricted BC → PPO → final evaluation chain and the remaining quality evidence is in docs/TEST.md. `run --phase bc`, `phase ppo` and `phase evaluate` run the phases separately, and an explicit `--force --reason` can skip BC eligibility while keeping the real gate results. Old formal experiments froze schema 4/v2, so old and new data and checkpoints do not migrate automatically.

Raw validation evidence lives in `verification/`, experiments and delivery artifacts live in `runs/` and `delivery/`, and every captured input — rule packages, human and teacher datasets, replay dumps, reference opponents — lives under `data/`; the source development package excludes raw validation results by default. The V4 weights, old experiments and the installed AI keep their historical state, and the new architecture is incompatible with schema 3 weights and optimizers.

For a clean Ubuntu 24.04 machine there is one extraction-ready archive: `python -m learning bundle --output PATH` writes it and `python -m learning verify-bundle ARCHIVE` checks it statically, and it carries no `.git`, virtual environment, run state, validation evidence, delivery output or raw replay dump. In an extracted copy `./setup.sh` installs the system packages, pinned torch 2.9.1, `_engine_lite` and Wesnoth 1.18.8 while starting no sampling or training, and `./train.sh` starts one experiment only on explicit user instruction. Building and verifying the archive prove installation only, never convergence or strength; the Ubuntu 24.04 runtime has not been executed yet and is tracked as `PKG1` in docs/TEST.md. Details are in [docs/bundle.md](docs/bundle.md).

## Development entry points

```bash
./setup.sh --device cpu
./run.sh --help
```

Training and collection start only on user instruction. After a change, verify only affected minimal behavior and reuse accepted evidence for items already passing; documentation work triggers no retraining, full test run or performance matrix.
