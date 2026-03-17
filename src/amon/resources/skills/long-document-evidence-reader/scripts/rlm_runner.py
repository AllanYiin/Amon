from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from context_store import ContextStore
from rlm_providers import ChatProvider, Message
from rlm_repl import ReplSession, extract_code_blocks


FINAL_RE = re.compile(
    r"\bFINAL\((?P<content>.*?)\)\s*$",
    re.DOTALL,
)
FINAL_VAR_RE = re.compile(
    r"\bFINAL_VAR\((?P<var>[A-Za-z_][A-Za-z0-9_]*)\)\s*$",
    re.DOTALL,
)


def _strip_wrapping_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


@dataclass
class RLMConfig:
    """Controls the RLM loop."""

    root_model: str
    sub_model: Optional[str] = None
    temperature: float = 0.2
    max_steps: int = 25
    repl_output_max_chars: int = 6000
    # How much to tell the root model about the environment each step
    include_locals_preview: bool = True


def default_system_prompt(
    *,
    context_type: str,
    context_total_length: int,
    context_lengths: List[int],
    subcalls_enabled: bool,
    batch_warning: bool = True,
) -> str:
    """System prompt template adapted from the paper's Appendix D.

    The key idea is to instruct the model that the *real context* lives in the REPL
    as `context`, and it can use code + (optional) `llm_query()` to interact with it.
    """

    base = f"""You are tasked with answering a query with associated context.
You can access, transform, and analyze this context interactively in a Python REPL environment.
You will be queried iteratively until you provide a final answer.

Your context is a {context_type} with {context_total_length} total characters,
and is broken up into chunks of char lengths: {context_lengths}.

The REPL environment is initialized with:
1. A `context` variable that contains extremely important information about your query.
2. The ability to use `print()` statements to view the output of your REPL code.
"""

    if subcalls_enabled:
        base += "3. A `llm_query(text: str) -> str` function that queries a sub-LLM inside the REPL.\n"

    base += """
You will only be able to see truncated outputs from the REPL environment.
Use variables as buffers to build up your final answer.

When you want to execute Python code, wrap it in triple backticks with a `repl` language identifier.
Example:
```repl
chunk = context[0].text[:1000]
print(chunk)
```

When you are done, you MUST provide a final answer using ONE of:
- FINAL(your answer)
- FINAL_VAR(variable_name)
"""

    if subcalls_enabled and batch_warning:
        base += """
IMPORTANT: `llm_query` is expensive. Batch related information into each call when possible.
Aim for ~50k-200k characters per call depending on your sub-model.
Avoid making one `llm_query` per line.
"""

    return base.strip()


class RecursiveLanguageModel:
    """A practical RLM implementation (REPL + optional recursive subcalls).

    This executes a loop:
    - Ask root LM for code / actions.
    - Execute code inside a persistent REPL where `context` lives.
    - Provide stdout/error back to root LM.
    - Stop when root LM emits FINAL(...) or FINAL_VAR(...).
    """

    def __init__(
        self,
        *,
        root: ChatProvider,
        sub: Optional[ChatProvider] = None,
        config: RLMConfig,
    ) -> None:
        self.root = root
        self.sub = sub
        self.config = config

    def run(self, query: str, context: ContextStore) -> str:
        subcalls_enabled = self.sub is not None and self.config.sub_model is not None

        # Build REPL with helpers.
        repl = ReplSession(output_max_chars=self.config.repl_output_max_chars)

        def llm_query(text: str, *, model: Optional[str] = None) -> str:
            if not subcalls_enabled:
                raise RuntimeError("Subcalls disabled (no sub provider / sub_model)")
            assert self.sub is not None
            use_model = model or self.config.sub_model
            assert use_model is not None
            msgs: List[Message] = [
                {"role": "system", "content": "You are a helpful sub-LLM. Follow the user's instructions precisely."},
                {"role": "user", "content": text},
            ]
            return self.sub.chat(
                msgs,
                model=use_model,
                temperature=self.config.temperature,
                max_tokens=2048,
            )

        repl.inject("context", context.chunks)
        repl.inject("ContextStore", ContextStore)
        repl.inject("llm_query", llm_query)

        sys_prompt = default_system_prompt(
            context_type="List[Chunk]",
            context_total_length=context.total_chars,
            context_lengths=context.chunk_lengths,
            subcalls_enabled=subcalls_enabled,
            batch_warning=True,
        )

        messages: List[Message] = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": f"QUERY:\n{query}\n\nReminder: Use the REPL to inspect `context` and then answer the query.",
            },
        ]

        last_repl_feedback = ""
        for step in range(1, self.config.max_steps + 1):
            if last_repl_feedback:
                messages.append(
                    {
                        "role": "user",
                        "content": f"REPL_FEEDBACK_STEP_{step-1}:\n{last_repl_feedback}",
                    }
                )

            assistant_text = self.root.chat(
                messages,
                model=self.config.root_model,
                temperature=self.config.temperature,
                max_tokens=4096,
            )
            messages.append({"role": "assistant", "content": assistant_text})

            # Check for FINAL
            final = self._try_parse_final(assistant_text, repl)
            if final is not None:
                return final

            # Execute repl blocks
            blocks = extract_code_blocks(assistant_text, langs={"repl", "python"})
            if not blocks:
                last_repl_feedback = (
                    "No code blocks found. Please either run `repl` code blocks to inspect `context`, "
                    "or provide FINAL(...)."
                )
                continue

            feedback_parts: List[str] = []
            for i, code in enumerate(blocks, start=1):
                result = repl.exec(code)
                feedback_parts.append(
                    f"[block {i}]\nCODE:\n{code}\n\nSTDOUT:\n{result.stdout or ''}\n\nERROR:\n{result.error or ''}".strip()
                )

            if self.config.include_locals_preview:
                preview = repl.locals_preview(max_items=25, max_value_chars=200)
                feedback_parts.append(f"LOCALS_PREVIEW:\n{preview}")

            last_repl_feedback = "\n\n---\n\n".join(feedback_parts)

        raise RuntimeError(
            f"RLM exceeded max_steps={self.config.max_steps} without producing FINAL(...)."
        )

    def _try_parse_final(self, text: str, repl: ReplSession) -> Optional[str]:
        m = FINAL_VAR_RE.search(text.strip())
        if m:
            var = m.group("var").strip()
            val = repl.get(var)
            if val is None:
                raise RuntimeError(f"FINAL_VAR({var}) requested, but variable not found in REPL")
            return str(val)

        m = FINAL_RE.search(text.strip())
        if m:
            content = m.group("content")
            return _strip_wrapping_quotes(content)

        return None
