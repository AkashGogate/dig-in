"""Old entry point, kept so earlier commands still work.

The DIG IN eval is now the Coval-style harness in eval/dig_in/
(personas x test sets x metrics x runs). Same flags: --mode mock|deepgram,
--confirm-billable, plus --test-set/--persona/--iterations/--max-audio-seconds/
--baseline. See docs/TESTING.md.
"""

import sys

from eval.dig_in.run import main

if __name__ == "__main__":
    sys.exit(main())
