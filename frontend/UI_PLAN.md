# Operator UI scope

The incoming UI branch is integrated as three focused operator pages while the existing workbench remains the default entry point. The branch’s visual tokens and original source are retained. Real behavior goes through the canonical backend.

## Implemented

- Server manual ordering from the canonical pinned menu, configured table/seat selection, editable quantities/modifier IDs/guest requests, saved revision review and separate human Confirm.
- Own active tickets with physical-unit pickup and optional whole-ticket delivered close-out.
- Distinct Kitchen ticket lineup, station filter, separate acknowledgment/start/ready, all per-unit guest context, actual physical zones and review warnings.
- Structured Kitchen-to-owner updates with explicit acknowledgement/resolution; staff-authored drafts survive polls.
- Explicit on-demand displayed summaries with generated/stale state; full workbench links for optional browser Print/Speak.
- Backend outage/HTTP rejection/uncertain exact retry states, role gates, explicit per-page staff selection, 401-triggered verified in-memory access fallback.
- Responsive layouts, visible focus, touch-size actions, escaped imported/staff-authored text and meaningful dependency-free behavior regressions.

## Retained in the full workbench

Menu PDF/photo extraction, correction, automatic encoding and reviewed activation; deliberate bounded microphone capture and low-confidence/table/dietary review; physical-zone camera simulator/adapter review and recovery; stock observation review/acceptance; explicit print and optional spoken summaries. Open the workbench, reselect staff and choose the same backend draft/ticket. No state is lost from the backend by page navigation.

## Unavailable pending a reviewed canonical contract

- Delivery preference is visibly disabled in the composer; the backend does not yet store it.
- Floor positioning/other-server guest detail, per-dish served completion, courses, helper/priority queues and shift navigation.
- Ambient/continuous listening, mock live-feed toggles, recognized speakers, undoing accepted food milestones and automatically interpreting an occupied zone as known food.
- Automatic chime/vibration or bulk pickup from a potentially stale banner. Current ready unit actions remain explicit.

Review source in [INTEGRATION](INTEGRATION.md). The original prototype is preserved under `prototypes/ui-abe9fb1` as unloaded `.txt` source for future contributors; its old integration assumptions are historical, not current contracts.
