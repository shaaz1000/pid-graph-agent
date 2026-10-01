"""Command-line entry point.

    uv run pid-agent tool <tool_name> '<json arguments>'   run one graph tool
    uv run pid-agent tools                                 list the available tools
    uv run pid-agent inspect                               summarise the loaded graphs

The natural-language agent is added on top of these tools in a later step.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from pid_agent.agent.tools import GraphTools, tool_specs
from pid_agent.config import load_settings
from pid_agent.errors import PidAgentError
from pid_agent.graph.service import GraphService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pid-agent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="log tool calls and timings")
    commands = parser.add_subparsers(dest="command", required=True)
    tool = commands.add_parser("tool", help="run one graph tool and print its structured result")
    tool.add_argument("name")
    tool.add_argument("arguments", nargs="?", default="{}", help="JSON object of tool arguments")
    commands.add_parser("tools", help="list tool definitions")
    commands.add_parser("inspect", help="summarise the pyDEXPI graphs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        if args.command == "tools":
            print(json.dumps(tool_specs(), indent=2))
            return 0
        settings = load_settings()
        if args.command == "inspect":
            from pid_agent.ingestion import graph_inspector

            graph_inspector.main()
            return 0
        try:
            arguments = json.loads(args.arguments)
        except json.JSONDecodeError as exc:
            print(f"error: tool arguments are not valid JSON: {exc}", file=sys.stderr)
            return 2
        tools = GraphTools(GraphService.from_file(settings.data_file, settings.max_traversal_depth))
        print(json.dumps(tools.call(args.name, arguments).to_dict(), indent=2, ensure_ascii=False))
        return 0
    except PidAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
