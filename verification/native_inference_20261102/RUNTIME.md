# Runtime dependency finding

The initial `REPORT.md` records passing benchmark thresholds before a follow-up reproducibility inspection. Its C1 PASS statement is insufficient for strict paired seeded acceptance: both initial extracted trees lacked `.runtime/entropy.so`, so `vendor/arena/match.py::_child_env` omitted `LD_PRELOAD` and `ARENA_ENTROPY_SEED`. The native binary's `--rng-seed` alone does not pin all native RNG sources, as already established in `verification/native_seed_20261031/REPORT.md`.

The initial six-game panels and their timings remain valid unseeded diagnostics, and the fixed-input speedup and three trained-model exact-output checks are unaffected. They do not demonstrate paired native trajectory equivalence. C1 remains open in the resident acceptance plan until the new seeded panels finish and their decisive event streams are compared.

New baseline and optimized directories are `native_inference_profile_seeded_20261102` and `native_inference_sparse_seeded_20261102` under `/home/tongshu/acceptance/`. Each is extracted from the same original source archive and compiles the existing `vendor/arena/entropy.c` using the unchanged `setup.sh` recipe. Source SHA-256 is `707dd06bf27494a7c5b17631486a14e71b16d7949eec2c5845c811259af80bd7`; resulting library SHA-256 is `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`. The sequential command is preserved in `native_timing_seeded.sh`, with the same seeds, gates and 1800-second ceiling per panel. The renewed check addresses this concrete missing dependency; it is not a retry to select a passing timing result.

The completed seeded result belongs in `REPORT_seeded.md`; do not rewrite these initial observations or their raw files.
