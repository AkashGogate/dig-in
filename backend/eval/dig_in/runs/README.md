# Evaluation provenance

`baseline-mock.json`, `baseline-mock.md`, and
`20261114-first-live-deepgram.json` are unchanged reports inherited from Voice
branch `9fcdd95`. They describe their recorded code and menu IDs, including the
older `bulldozer`/`backhoe` IDs. They are historical evidence, not results for the
combined application or its current confidence handling. The live report used
synthetic speech; it does not establish real kitchen or microphone performance.

Current test sets use canonical `the_bulldozer`/`the_backhoe` IDs. New prerecorded
runs pass the same conservative confidence metadata into the live-mode domain
commands as the streaming client. Missing confidence requires human review.
Controlled metadata cases are marked synthetic and have no speech-error score.
The old fixed transcript cases exercise parser regressions; they cannot prove
confidence behavior because their original confidence metadata was not retained.

Run output stays ignored unless deliberately reviewed. Default mode is free and
does not render audio or call providers. Paid mode requires `--confirm-billable`
and a positive finite audio cap; comparisons use unrounded sample durations.
Simulated domain execution always uses local menu embeddings and makes no STT
calls. Confidence thresholds and synthetic audio remain provisional validation.
