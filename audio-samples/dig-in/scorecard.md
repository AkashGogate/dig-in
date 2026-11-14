# DIG IN voice eval scorecard (mock)

MOCK: ground-truth text fed to the parser. Proves plumbing/scoring, not speech accuracy.

| Flow | Condition | Passed |
| --- | --- | --- |
| kitchen | clean | 2/2 |
| kitchen | noise | 2/2 |
| kitchen | overlap | 2/2 |
| server | clean | 4/4 |
| server | noise | 4/4 |
| server | overlap | 4/4 |

**Total: 18/18**

| Clip | Pass | Heard |
| --- | --- | --- |
| server_two_dishes_modifier__clean | PASS | Table four, two bulldozers, hold the pickles, and one dirt site |
| server_two_dishes_modifier__noise | PASS | Table four, two bulldozers, hold the pickles, and one dirt site |
| server_two_dishes_modifier__overlap | PASS | Table four, two bulldozers, hold the pickles, and one dirt site |
| server_internal_and__clean | PASS | Table two, one mac and cheese and three tots |
| server_internal_and__noise | PASS | Table two, one mac and cheese and three tots |
| server_internal_and__overlap | PASS | Table two, one mac and cheese and three tots |
| server_table_mismatch__clean | PASS | Table three, one backhoe without slaw |
| server_table_mismatch__noise | PASS | Table three, one backhoe without slaw |
| server_table_mismatch__overlap | PASS | Table three, one backhoe without slaw |
| server_misheard_name__clean | PASS | Table one, one bull dozer |
| server_misheard_name__noise | PASS | Table one, one bull dozer |
| server_misheard_name__overlap | PASS | Table one, one bull dozer |
| kitchen_heard__clean | PASS | Heard, table four |
| kitchen_heard__noise | PASS | Heard, table four |
| kitchen_heard__overlap | PASS | Heard, table four |
| kitchen_start__clean | PASS | Start table four bulldozer |
| kitchen_start__noise | PASS | Start table four bulldozer |
| kitchen_start__overlap | PASS | Start table four bulldozer |
