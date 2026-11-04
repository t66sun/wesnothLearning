# WesnothLearning

> Language: English | [中文](docs/README_zh.md)

Three independent models for Wesnoth 1.18.8: single combat `duel`, four-player free-for-all `ffa4` and team `team2v2`. Training uses Python/PyTorch with the native game and a Rust lite engine; the final artifact deploys as a pure Lua AI inside the native game.

## Documentation

- [Architecture and parameters](docs/architecture.md): the current implementation, its contracts and limits.
- [Pending acceptance list](docs/TEST.md): only acceptance work that is still open, with the smallest Ubuntu procedure for each.
- [Agent training operations guide](docs/instructions.md): taking over the environment, start/resume, maintenance, diagnosis and instruction-driven tuning.
- [Provenance and licensing](docs/THIRD_PARTY.md): third-party code, reference competitor packages and official component licenses.

Captured inputs live in `data/`, training state in `runs/`, exported models in `delivery/`, and acceptance evidence in `verification/`.

## Development entry points

```bash
./setup.sh --device cpu
./run.sh --help
```

Start training or collection only on user instruction.
