# Voice increment integration

Incoming9fcdd959ca86a394aff55c5996392a7a5bd5a076 merged after d5646f5.
Preserved prior pinned-menu, PCM/sample/pacing quotas, device-bound ticket,
role/session/capture cancellation and dietary attachment/deletion safeguards.

Added table-slot homophones and disabled smart formatting that merged table and
quantity. Shared transcript_confidence uses minimum finalized-word confidence;
any missing/nonfinite/invalid word or final segment remains unknown. Explicit
live mode with unknown/<0.6 confidence requires Server full-draft review and
Kitchen clarification, never an automatic state change. Typed mock remains usable.
Confidence is a client-supplied review hint, not authenticated provider proof.

Current revision reviewed_speech action is explicit; human Confirm remains a
separate tap. Global401 fallback verifies tab credentials without persistence,
works locally and does not duplicate a successful native hosted Basic sign-in.

New Coval-style harness preserves historical reports, migrates active canonical
menu IDs, evaluates domain confidence and duplicate units, redacts usage keyterms
and enforces exact positive finite duration caps. Regenerated audio/routine runs
are ignored. Empty/nonfinite cache/render is rejected before provider calls.
A sandboxed say render produced empty files; they were removed and regenerated
with local speech synthesis allowed. No provider audio was sent in that failure.

Focused Voice57 and eval30 cases passed; MOCK26:18exact/8flagged/0wrong, safetyPASS.
A protected v2 WebSocket probe sent one1.82s synthetic clip to real Deepgram:
expected dish matched, confidence0.8691406, draft-only, no review flags; backend
estimated chargeUSD0.0002. Physical mic, room noise, phone/headphones remain separate.
Root STATUS records final full suite, matrix and hosted/container results.
