"""DIG IN voice eval, structured like Coval (docs.coval.dev).

personas.json   HOW the speaker sounds (voice, rate, noise, overlap, line quality).
test_sets/      WHAT is said and the expected outcome (Server orders, Kitchen
                callouts, safety regressions from real live transcripts).
metrics.py      deterministic pass/fail functions; `wrong` (a silently wrong
                accepted result) is a hard gate that must stay 0.
simulate.py     one simulation = case x persona x iteration through the real
                parser/core domain.
run.py          a run = test sets x personas x mode with a fixed agent config;
                writes runs/<run_id>.json + .md and diffs against a baseline.
"""
