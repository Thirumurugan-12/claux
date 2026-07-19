"""Print the Anthropic tool-use schemas the registry emits.

    python -m app.tools

Acceptance (P9): I can print the generated tool schemas — this is exactly what P14's
orchestration loop hands to the Claude API.
"""

from __future__ import annotations

import json
import sys

from app.tools.catalog import build_registry


def main() -> int:
    registry = build_registry()
    print(json.dumps(registry.anthropic_schemas(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
