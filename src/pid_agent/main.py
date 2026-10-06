"""Command-line entry point.

    uv run pid-agent "What is P4711 connected to?"      answer one question, with its trace
    uv run pid-agent                                     interactive prompt
    uv run pid-agent tool <name> '<json arguments>'      run one graph tool directly (no LLM)
    uv run pid-agent tools                               print the tool definitions
    uv run pid-agent inspect                             summarise the loaded graphs
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from pathlib import Path

from pid_agent.agent.tools import GraphTools, tool_specs
from pid_agent.config import Settings, load_settings
from pid_agent.errors import PidAgentError
from pid_agent.graph.service import GraphService

COMMANDS = ("tool", "tools", "inspect")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pid-agent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="log tool calls, model calls and timings")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    parser.add_argument("--no-trace", action="store_true", help="print only the answer")
    parser.add_argument("--pid", metavar="FILE", help="DEXPI/Proteus XML file to load (default: PID_DATA_FILE or the C01 reference P&ID)")
    parser.add_argument("words", nargs="*", help="a question, or one of: tool, tools, inspect")
    return parser


def _graph_tools(settings: Settings) -> GraphTools:
    return GraphTools(GraphService.from_file(settings.data_file, settings.max_traversal_depth))


def _run_tool(settings: Settings, words: list[str]) -> int:
    if not words:
        print("usage: pid-agent tool <name> '<json arguments>'", file=sys.stderr)
        return 2
    try:
        arguments = json.loads(words[1]) if len(words) > 1 else {}
    except json.JSONDecodeError as exc:
        print(f"error: tool arguments are not valid JSON: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_graph_tools(settings).call(words[0], arguments).to_dict(), indent=2, ensure_ascii=False))
    return 0


def _build_agent(settings: Settings):
    from pid_agent.agent.workflow import PidAgent
    from pid_agent.llm import create_llm

    llm = create_llm(settings)  # fails early, with a clear message, if the key is missing
    return PidAgent(llm, _graph_tools(settings), answer_mode=settings.answer_mode)


def _answer(agent, question: str, args: argparse.Namespace) -> None:
    from pid_agent.agent.workflow import format_transcript

    result = agent.ask(question)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.no_trace:
        print(result.answer)
    else:
        print(format_transcript(result))


def _interactive(agent, args: argparse.Namespace) -> None:
    print("P&ID agent. Ask a question about the plant (empty line or Ctrl-D to quit).")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            return
        _answer(agent, question, args)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    words: list[str] = args.words
    try:
        if words[:1] == ["tools"]:
            print(json.dumps(tool_specs(), indent=2))
            return 0
        settings = load_settings()
        if args.pid:
            settings = dataclasses.replace(settings, data_file=Path(args.pid).expanduser())
        if words[:1] == ["inspect"]:
            from pid_agent.ingestion import graph_inspector

            graph_inspector.main(settings.data_file)
            return 0
        if words[:1] == ["tool"]:
            return _run_tool(settings, words[1:])
        agent = _build_agent(settings)
        if words:
            _answer(agent, " ".join(words), args)
        else:
            _interactive(agent, args)
        return 0
    except PidAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
