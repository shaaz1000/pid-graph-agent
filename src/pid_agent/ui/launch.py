"""`uv run pid-agent-ui`: start the local Streamlit chat interface."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    try:
        from streamlit.web import cli
    except ImportError:
        print("error: the UI needs Streamlit. Install it with: uv sync --group ui", file=sys.stderr)
        return 1
    app = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app), "--browser.gatherUsageStats=false", "--client.toolbarMode=minimal", *sys.argv[1:]]
    return cli.main()


if __name__ == "__main__":
    sys.exit(main())
