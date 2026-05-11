import os
from dataclasses import dataclass

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ReadRequest

from .dispatch import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
    agents_md_path: str = ""
    bin_sql_content: str = ""


# Few-shot user→assistant pair — strongest signal for JSON-only output.
# Placed immediately after system prompt so the model sees its own expected format
# before any task context.
_FEW_SHOT_USER = "Example: How many catalogue products are Lawn Mower?"
_FEW_SHOT_ASSISTANT = (
    '{"current_state":"validating SQL syntax before executing count",'
    '"plan_remaining_steps_brief":["EXPLAIN query","SELECT COUNT","report result"],'
    '"done_operations":[],"task_completed":false,'
    '"function":{"tool":"exec","path":"/bin/sql",'
    '"args":["EXPLAIN SELECT COUNT(*) FROM products WHERE type=\'Lawn Mower\'"],'
    '"stdin":""}}'
)


def run_prephase(
    vm: EcomRuntimeClientSync,
    task_text: str,
    system_prompt_text: str,
    task_id: str = "",
    dry_run: bool = False,
) -> PrephaseResult:
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

    log: list = [
        {"role": "system", "content": system_prompt_text},
        {"role": "user", "content": _FEW_SHOT_USER},
        {"role": "assistant", "content": _FEW_SHOT_ASSISTANT},
    ]

    # Read AGENTS.MD — source of truth for vault semantics and folder roles.
    agents_md_content = ""
    agents_md_path = ""
    for candidate in ("/AGENTS.MD", "/AGENTS.md"):
        try:
            r = vm.read(ReadRequest(path=candidate))
            if r.content:
                agents_md_content = r.content
                agents_md_path = candidate
                print(f"{CLI_BLUE}[prephase] read {candidate}:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
                break
        except Exception:
            pass

    prephase_parts = [f"TASK: {task_text}"]
    if agents_md_content:
        if _LOG_LEVEL == "DEBUG":
            print(f"{CLI_BLUE}[prephase] AGENTS.MD content:\n{agents_md_content}{CLI_CLR}")
        prephase_parts.append(
            f"\n{agents_md_path} CONTENT (source of truth for vault semantics):\n{agents_md_content}"
        )
    prephase_parts.append(
        "\nNOTE: Use AGENTS.MD above to identify actual folder paths. "
        "Verify paths with list/find before acting. Do not assume paths."
    )

    log.append({"role": "user", "content": "\n".join(prephase_parts)})
    preserve_prefix = list(log)

    bin_sql_content = ""
    if dry_run:
        try:
            bin_r = vm.read(ReadRequest(path="/bin/sql"))
            bin_sql_content = bin_r.content or ""
            print(f"{CLI_BLUE}[prephase] read /bin/sql:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
        except Exception as e:
            print(f"{CLI_YELLOW}[prephase] /bin/sql: {e}{CLI_CLR}")

    print(f"{CLI_BLUE}[prephase] done{CLI_CLR}")

    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        bin_sql_content=bin_sql_content,
    )
