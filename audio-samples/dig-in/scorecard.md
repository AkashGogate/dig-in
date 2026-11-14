# DIG IN voice eval scorecard (deepgram)

DEEPGRAM: real nova-3 transcription of synthetic say clips (not a real kitchen).

| Flow | Condition | Passed |
| --- | --- | --- |
| kitchen | clean | 1/2 |
| kitchen | noise | 0/2 |
| kitchen | overlap | 0/2 |
| server | clean | 4/4 |
| server | noise | 2/4 |
| server | overlap | 1/4 |

**Total: 8/18**

| Clip | Pass | Heard |
| --- | --- | --- |
| server_two_dishes_modifier__clean | PASS | Table four two bulldozers hold the pickles and one dirt site |
| server_two_dishes_modifier__noise | PASS | Table four two bulldozers hold the pickles and one dirt site |
| server_two_dishes_modifier__overlap | PASS | Table four, two bulldozers, hold the pickles, and one dirt site. |
| server_internal_and__clean | PASS | Table two one mac and cheese and three tots |
| server_internal_and__noise | PASS | Table two one mac and cheese and three tots |
| server_internal_and__overlap | FAIL | Table two one mac and cheese and three tots table nine |
| server_table_mismatch__clean | PASS | Table three, one backhoe without slaw. |
| server_table_mismatch__noise | FAIL | Table 31 backhoe without slaw |
| server_table_mismatch__overlap | FAIL | Table 31 Backho without swab table 9 |
| server_misheard_name__clean | PASS | Table one, one bulldozer. |
| server_misheard_name__noise | FAIL | Table 11 bulldozer |
| server_misheard_name__overlap | FAIL | Table one. One bulldozer. Refill for table nine. |
| kitchen_heard__clean | PASS | Heard. Table four. |
| kitchen_heard__noise | FAIL | PERT, table four. |
| kitchen_heard__overlap | FAIL | Heard table four. Grab a refill for table nine. |
| kitchen_start__clean | FAIL | Start table for bulldozer |
| kitchen_start__noise | FAIL | Start table for bulldozer |
| kitchen_start__overlap | FAIL | Start table four bulldozer grab a refill for table nine |
