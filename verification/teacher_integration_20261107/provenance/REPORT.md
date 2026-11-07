# Teacher provenance and mixed-format export acceptance

Ubuntu source `e036c2c1e226bceda85474c351ee78934da10146` passed 25 checks in 9.917 seconds. The preceding implementation `fe18dc2db8f6` passed 22 checks; review then identified missing platform-independent ZIP metadata, bounded-read bucket ordering, and anchor identity assertions. The final checks include those regressions.

Each adjacent check directory preserves the exact source, command, output and exit status. Sources were shipped as commit archives to fresh directories on `cpuServer`; the installed acceptance extension and existing filtered rules were reused. No games, optimizer updates or formal collection ran.

Accepted scope: versioned teacher provenance for covered and uncovered rows; legacy read compatibility; unchanged teacher/human and original/DAgger sampler behavior; bounded-read ordering; exclusion of the actual control teacher from rehearsal; BC anchor identity; and per-format checkpoint/export metadata. The export assembly test mocks package generation and numerical verification: numerical export correctness is covered only by the existing affected audit regressions, not by the metadata fixture.

Native/Lite runtime stamping, role wiring, hard budgets and the authorized 48-game panel remain pending. The runtime still rejects the mixed set and Astra remains the default. This evidence grants neither BC qualification nor a strength claim.
