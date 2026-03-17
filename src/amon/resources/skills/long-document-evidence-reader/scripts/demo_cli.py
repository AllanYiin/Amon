#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from load_codebase import load_repo_as_context
from load_pdf import load_pdf_as_context
from rlm_providers import OpenAIChatProvider
from rlm_runner import RLMRunner


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Demo CLI for the RLM long-context reader skill"
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=str, help="Path to a PDF file")
    src.add_argument("--repo", type=str, help="Path to a code repository folder")
    p.add_argument("--question", type=str, required=True, help="User query to answer")
    p.add_argument("--root-model", type=str, default="gpt-4.1", help="Root model")
    p.add_argument("--sub-model", type=str, default="gpt-4.1-mini", help="Sub model")
    p.add_argument("--max-steps", type=int, default=12, help="Max root iterations")
    p.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("OPENAI_API_KEY", ""),
        help="OpenAI API key (or set OPENAI_API_KEY)",
    )
    p.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        help="Optional path to a custom system prompt (see references/system_prompts.md)",
    )
    return p


def main() -> int:
    args = build_argparser().parse_args()

    if not args.api_key:
        raise SystemExit(
            "Missing OpenAI API key. Provide --api-key or set OPENAI_API_KEY."
        )

    provider = OpenAIChatProvider(api_key=args.api_key)
    runner = RLMRunner(
        root_provider=provider,
        sub_provider=provider,
        root_model=args.root_model,
        sub_model=args.sub_model,
        max_steps=args.max_steps,
    )

    if args.system_prompt:
        runner.system_prompt = Path(args.system_prompt).read_text(encoding="utf-8")

    if args.pdf:
        context = load_pdf_as_context(Path(args.pdf))
    else:
        context = load_repo_as_context(Path(args.repo))

    result = runner.run(query=args.question, context=context)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
