# Curated lobby-archive corpus — usability audit, 2026-10-30

Question: the 434 games in `data/replays_curated/` were selected by container and
format gates. Are they *usable*, or only well-formed?

Environment: Windows reference box, no Wesnoth install. Ubuntu acceptance
**NOT RUN**; no game was replayed. Numbers in `audit.json`.

## What is verified

- Container integrity: 434/434 curated `.gz` payloads rehash to the recorded
  `payload_sha256`; 434 families for 434 files, so no history is duplicated and
  no earlier save was left in beside its continuation.
- Structure: all 434 use `layout=archive`, `category=standard_multiplayer`,
  `initial_turn=1`, an 8-digit initial RNG seed, and every one has 0 AI sides —
  both seats are human on every board.
- History shape: every game contains `move`, `recruit` and `end_turn`; 412 also
  contain `attack`; 147,899 decisions total, 23 to 1,326 per game; no game
  records more decisions than semantic commands.
- Integrity hooks: 432 games carry per-action `checkup` (148,948 in total, 99.3%
  of decisions) and 2 carry `mp_checkup` instead; 235 games carry an end marker.

## What is not verified, and cannot be here

No file was replayed under native 1.18.8, so legality, roll reproduction and
out-of-sync behaviour are unproven; nothing shows that these histories can be
turned into observations and candidates. Beyond that, `learning/human.py`
rejects every file at `other_version` (none is 1.18.8) and then at
`missing_native_initial_state` (no `[replay_start]`, so `prepare_capture` has
nothing to hang its observer on). The corpus is staging, not importable data.

## Defect found by this audit

The server announces "X takes control of side N." in three situations: a lobby
slot being filled before play, a seat changing hands mid-game, and the lobby
reopening after the game. Only the middle one mixes two humans in one history.

Detected as an announcement bracketed by that side's decisions and naming
someone other than its initial player:

| Defect | Games | Detail |
| --- | --- | --- |
| controller changed mid-game | 116 | 190 side hand-overs; one game records 14 |
| one player on both sides | 8 | 1 of them also changed hands |
| clean of both | 311 | 97,091 decisions; 268 duel, 43 team2v2 |

A hand-over that happens after that side's last decision is post-game lobby
chatter and is deliberately not counted — 432 of 434 games end with such a
message, and treating it as a provenance change would condemn the whole corpus.

`learning/human.compatibility` guards exactly this with
`controller_provenance_changed`; without the filter, 123 of 434 games would mix
decisions from humans the label claims are two.

## Consequence

`replay_curate` now records `controller_changes` (side to the names that took
it over) and the note `controller_changed_midgame; human_side_provenance_mixed`
instead of staying silent. Selection is unchanged: the curator records quality
defects and never drops on them, so a consumer that needs clean provenance
filters on the field. The BC corpus question therefore narrows to 311 games and
97,091 decisions, and stays blocked on the rules version regardless.

## Limits

- Reference evidence only; board identity is still a terrain-multiset match and
  no replay was executed.
- A hand-over is inferred from server chatter naming a side; a takeover
  announced only in the lobby UI, without a speak command, would be missed.
