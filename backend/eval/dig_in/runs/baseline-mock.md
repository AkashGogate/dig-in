# DIG IN voice run 20261114T234910Z-mock

MOCK: scripted text fed to the real parser/domain (persona-independent). Proves plumbing and scoring, not speech accuracy.

mode mock | commit 63bff91 | 2026-11-14T23:49:10+00:00 | billable audio 0.0 s

Outcomes: **exact** = intended result; **flagged** = blocked or asked, a human steps in (safe);
**wrong** = accepted silently with the wrong content or kitchen state change (hard gate: must be 0).

| Persona | Test set | Sims | Exact | Flagged | Wrong | Passed | Item recall | WER |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| recorded_transcript | safety_regressions | 7 | 1 | 6 | 0 | 7 | 0.571 | 0.734 |
| scripted_text | kitchen_callouts | 9 | 9 | 0 | 0 | 9 | 1.0 | None |
| scripted_text | server_orders | 8 | 8 | 0 | 0 | 8 | 1.0 | None |

**Total: 24 sims, 18 exact, 6 flagged, 0 wrong; gate PASS**

| Test set | Case | Persona | Outcome | Heard |
| --- | --- | --- | --- | --- |
| kitchen_callouts | heard | scripted_text | exact | Heard, table four |
| kitchen_callouts | heard_filler | scripted_text | exact | Heard table four, thanks |
| kitchen_callouts | start | scripted_text | exact | Start table four bulldozer |
| kitchen_callouts | start_with_quantity | scripted_text | exact | Start table four, one bulldozer |
| kitchen_callouts | start_homophone_table | scripted_text | exact | Start table for bulldozer |
| kitchen_callouts | repeated_dish_asks | scripted_text | exact | Start table four bulldozer |
| kitchen_callouts | same_table_two_orders_asks | scripted_text | exact | Heard, table two |
| kitchen_callouts | misheard_dish_suggested_on_ticket | scripted_text | exact | Start table three back hoe |
| kitchen_callouts | wrong_table_not_touched | scripted_text | exact | Heard, table one |
| safety_regressions | merged_number_table_31 | recorded_transcript | flagged | Table 31 backhoe without slaw |
| safety_regressions | merged_number_table_11 | recorded_transcript | flagged | Table 11 bulldozer |
| safety_regressions | overlap_appended_to_order | recorded_transcript | flagged | Table two one mac and cheese and three tots table nine |
| safety_regressions | heard_misheard_as_pert | recorded_transcript | flagged | PERT, table four. |
| safety_regressions | table_for_homophone | recorded_transcript | exact | Start table for bulldozer |
| safety_regressions | overlap_after_heard | recorded_transcript | flagged | Heard table four. Grab a refill for table nine. |
| safety_regressions | overlap_after_start | recorded_transcript | flagged | Start table four bulldozer grab a refill for table nine |
| server_orders | two_dishes_modifier | scripted_text | exact | Table four, two bulldozers, hold the pickles, and one dirt site |
| server_orders | internal_and | scripted_text | exact | Table two, one mac and cheese and three tots |
| server_orders | table_mismatch | scripted_text | exact | Table three, one backhoe without slaw |
| server_orders | misheard_name | scripted_text | exact | Table one, one bull dozer |
| server_orders | seat_and_allergy | scripted_text | exact | Table two, one bulldozer, seat two, allergy to gluten |
| server_orders | no_allergies | scripted_text | exact | Table two, one bulldozer and no allergies |
| server_orders | two_modifiers | scripted_text | exact | Table one, one bulldozer, no onions, sauce on the side |
| server_orders | homophone_table | scripted_text | exact | Table for, one steel beams |
