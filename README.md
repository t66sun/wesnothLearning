# WesnothLearning

> Language: English | [中文](docs/README_zh.md)

Three independent models for Wesnoth 1.18.8: single combat `duel`, four-player free-for-all `ffa4` and team `team2v2`. Training uses Python/PyTorch with the native game and a Rust lite engine; the final artifact deploys as a pure Lua AI inside the native game.

## Documentation

- [Architecture and parameters](docs/architecture.md): the current implementation, its contracts and limits.
- [Pending acceptance list](docs/TEST.md): only acceptance work that is still open, with the smallest Ubuntu procedure for each.
- [Agent training operations guide](docs/instructions.md): taking over the environment, start/resume, maintenance, diagnosis and instruction-driven tuning.
- [Provenance and licensing](docs/THIRD_PARTY.md): third-party code, reference competitor packages and official component licenses.

BC teacher-game targets are **300** duel, **600** FF4 and **400** 2v2 at the default of **8 global workers**. A new manifest freezes the sole custom teacher, the `gpt6astra` package, so teacher games, DAgger corrections and exports share one identity; a lite run collects those teacher games (`native_bc_games` defaults to 0). No formal training is currently running.

The Rust rule core, spatial/relational/memory model, BC/PPO, online reward control and pure Lua export are all implemented. New experiments use lite by default with the 587 units and 438 terrains of `data/rules/1.18.8-training`, gated at startup by the 158-unit six-faction training closure, with the declared teacher identity frozen in each manifest. Boundaries for full campaign behavior, full-pipeline performance and formal training strength are in the architecture document.

The current implementation is schema 5 / candidate v3, adding the public tactical inputs needed for four-player BC; Ubuntu has passed a restricted BC → PPO → final evaluation chain; the remaining acceptance work is in docs/TEST.md. `run --phase bc`, `phase ppo` and `phase evaluate` run the phases separately, and an explicit `--force --reason` can skip BC eligibility while keeping the real gate results. Old formal experiments froze schema 4/v2, so old and new data and checkpoints do not migrate automatically.

Raw validation evidence lives in `verification/`, experiments and delivery artifacts live in `runs/` and `delivery/`, and every captured input — rule packages, human and teacher datasets, replay dumps, reference opponents — lives under `data/`; the source development package excludes raw validation results by default. The V4 weights, old experiments and the installed AI keep their historical state, and the new architecture is incompatible with schema 3 weights and optimizers.

For a clean Ubuntu 24.04 machine there is one extraction-ready archive: `python -m learning bundle --output PATH` writes it and `python -m learning verify-bundle ARCHIVE` checks it statically, and it carries no `.git`, virtual environment, run state, validation evidence, delivery output or raw replay dump. In an extracted copy `./setup.sh` installs the system packages, pinned torch 2.9.1, `_engine_lite` and Wesnoth 1.18.8 while starting no sampling or training, and `./train.sh` starts one experiment only on explicit user instruction. Building and verifying the archive prove installation only, never convergence or strength; the Ubuntu 24.04 runtime has never been executed, and the operator dropped that acceptance (`PKG1`) on 2026-10-31, so no bundle acceptance exists or is planned (`verification/acceptance_20261030/REPORT.md`). Details are in [docs/instructions.md](docs/instructions.md#clean-ubuntu-2404-training-bundle).

## Development entry points

```bash
./setup.sh --device cpu
./run.sh --help
```

Training and collection start only on user instruction. After a change, verify only affected minimal behavior and reuse accepted evidence for items already passing; documentation work triggers no retraining, full test run or performance matrix.
