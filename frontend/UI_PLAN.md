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

## Kitchen glanceability increment — UI163d9e8

The latest teammate Kitchen redesign is integrated through the existing canonical renderer, retaining its CSS and visual hierarchy: calm dark ticket columns, bold table labels, prominent dish names, quiet seat/physical-zone/station/modifier metadata, consistent right-aligned stage chips and restrained status color. Tickets sort oldest sent first. Neutral submission-age timers turn orange at 10 minutes and red at 15; missing submission/start times remain unknown, and no timer claims doneness. Per-unit elapsed/known typical time stays visible.

A green ticket accent appears only when every physical unit on the full ticket is currently ready, still owns its assigned physical zone and has no zone review pending. Station filters change visible units, while ticket ready ratios always use the complete physical ticket. The bottom bar counts current active units, excluding picked-up/delivered history; it is deliberately not labeled “All day.” Exact guest requests remain visible in each dish row. Unit IDs, outgoing update composition and summaries use secondary disclosure controls to keep the line easy to scan; typed notes/open state and keyboard focus survive polls. Long tickets remain reachable by document scrolling, and narrow screens stack tickets vertically.

No fabricated last-heard/Undo, microphone, source icon, delivery preference or camera feed is introduced. Current `/api/v2` authority, per-unit tap controls, physical-zone review, actor/credential guards, uncertain exact retry and explicit summaries are unchanged. The newest original teammate source/docs remain preserved as unloaded `.txt` reference in `prototypes/ui-163d9e8/` alongside the earlier archive.
