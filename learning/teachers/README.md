# Derived Astra teacher

`gpt6astra/` is a source copy of the frozen package
`data/opponents/gpt6astra.zip` (`sha256` recorded by
`learning.teachers.parent_digest`). The archive itself is never edited.

The copy is adapted only where the lite rules changed: attack scoring uses the
deterministic `expected_damage_v1` results, slow is worth 25% damage plus its
movement restriction, and poison is worth six points per tick. Recruitment,
movement, team and targeting structure stay upstream. `lua/value.lua` holds
those values once; `duel.lua`, `four.lua` and `eight.lua` call it.

The lite host always loads this source, so a job that names the frozen archive
still runs the adapted teacher. `learning.teachers.build(path)` writes a
deployable archive from the source for native or external use. A derived
archive is a build artifact and is not committed.

The source hash travels in lite rows, checkpoints, job metadata and exports as
`teacher_profile` plus `teacher_source_sha256`; a run cannot mix rows from a
different teacher profile.
