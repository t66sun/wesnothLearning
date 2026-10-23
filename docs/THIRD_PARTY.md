# Provenance and licensing

> Language: English | [中文](THIRD_PARTY_zh.md)

`vendor/arena/` comes from the parent read-only WesnothArena native v2 SDK and keeps its MIT LICENSE and third-party notices. The training project and the team extension are provided under the same MIT license.

The four zips in `opponents/` are the user-specified reference players' original packages, stored unchanged; each experiment copies them again and freezes their hashes. Licensing of competitor sources and weights is stated by each submitter.

This project does not bundle the Wesnoth game itself or the official RCA implementation. The install script downloads and verifies the 1.18.8 sources from the official release address and builds them locally on the user's server; official components follow their own licenses.

No third-party training framework or model from the reference directory `dev/upstream` has been copied.
