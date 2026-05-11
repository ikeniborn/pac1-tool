import os
import re
from dataclasses import dataclass

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ContextRequest, ExecRequest, ListRequest, ReadRequest, TreeRequest

from .dispatch import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW
from .prompt import SYSTEM_PROMPT

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""


def _format_tree_entry(entry, prefix: str = "", is_last: bool = True) -> list[str]:
    branch = "└── " if is_last else "├── "
    lines = [f"{prefix}{branch}{entry.name}"]
    child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
    children = list(entry.children)
    for idx, child in enumerate(children):
        lines.extend(_format_tree_entry(child, prefix=child_prefix, is_last=idx == len(children) - 1))
    return lines


def _render_tree_result(result, root_path: str = "/", level: int = 2) -> str:
    root = result.root
    if not root.name:
        body = "."
    else:
        lines = [root.name]
        children = list(root.children)
        for idx, child in enumerate(children):
            lines.extend(_format_tree_entry(child, is_last=idx == len(children) - 1))
        body = "\n".join(lines)
    level_arg = f" -L {level}" if level > 0 else ""
    return f"tree{level_arg} {root_path}\n{body}"


_FEW_SHOT_USER = "Example: what files are in the notes folder?"
_FEW_SHOT_ASSISTANT = (
    '{"current_state":"listing notes folder to identify files",'
    '"plan_remaining_steps_brief":["list /notes","act on result"],'
    '"done_operations":[],"task_completed":false,'
    '"function":{"tool":"list","path":"/notes"}}'
)


def run_prephase(
    vm: EcomRuntimeClientSync,
    task_text: str,
    _system_prompt_text: str = "",  # noqa: ARG001
) -> PrephaseResult:
    """Build initial conversation log: tree + AGENTS.MD + auto-preload + SQL schema."""
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

    log: list = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _FEW_SHOT_USER},
        {"role": "assistant", "content": _FEW_SHOT_ASSISTANT},
    ]

    # Step 1: tree -L 2 /
    print(f"{CLI_BLUE}[prephase] tree -L 2 /...{CLI_CLR}", end=" ")
    tree_txt = ""
    tree_result = None
    try:
        tree_result = vm.tree(TreeRequest(root="/", level=2))
        tree_txt = _render_tree_result(tree_result, root_path="/", level=2)
        print(f"{CLI_GREEN}ok{CLI_CLR}")
    except Exception as e:
        tree_txt = f"(tree failed: {e})"
        print(f"{CLI_YELLOW}failed: {e}{CLI_CLR}")

    # Step 2: read AGENTS.MD
    agents_md_content = ""
    agents_md_path = ""
    candidates = ["/AGENTS.MD", "/AGENTS.md"]
    if tree_result is not None:
        for entry in tree_result.root.children:
            if entry.children:
                for variant in ("AGENTS.MD", "AGENTS.md"):
                    candidates.append(f"/{entry.name}/{variant}")
    for candidate in candidates:
        try:
            r = vm.read(ReadRequest(path=candidate))
            if r.content:
                agents_md_content = r.content
                agents_md_path = candidate
                print(f"{CLI_BLUE}[prephase] read {candidate}:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
                break
        except Exception:
            pass

    # Step 3: auto-preload dirs referenced in AGENTS.MD
    docs_content_parts: list[str] = []
    if agents_md_content and tree_result is not None:
        top_level_dirs = {entry.name for entry in tree_result.root.children}
        mentioned = set(re.findall(r'`?(\w[\w-]*)/`?', agents_md_content))
        # proc/catalog and proc/stores are covered by SQL — skip to avoid loading entire catalog
        _skip = {"contacts", "accounts", "opportunities", "reminders", "my-invoices", "outbox", "inbox", "proc"}
        to_preload = sorted((mentioned & top_level_dirs) - _skip)
        if to_preload:
            print(f"{CLI_BLUE}[prephase] referenced dirs to preload: {to_preload}{CLI_CLR}")

        def _read_dir(dir_path: str, seen: set) -> None:
            try:
                entries = vm.list(ListRequest(path=dir_path))
            except Exception as e:
                print(f"{CLI_YELLOW}[prephase] {dir_path}/: {e}{CLI_CLR}")
                return
            for entry in entries.entries:
                if entry.name.startswith("_") or entry.name.upper() == "README.MD":
                    continue
                child_path = f"{dir_path}/{entry.name}"
                if child_path in seen:
                    continue
                seen.add(child_path)
                try:
                    file_r = vm.read(ReadRequest(path=child_path))
                    if file_r.content:
                        _fc = file_r.content
                        if len(_fc) >= 500:
                            _fc += f"\n[PREPHASE EXCERPT — content may be partial. For exact counts or full content use: read('{child_path}')]"
                        docs_content_parts.append(f"--- {child_path} ---\n{_fc}")
                        print(f"{CLI_BLUE}[prephase] read {child_path}:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
                        if _LOG_LEVEL == "DEBUG":
                            print(f"{CLI_BLUE}[prephase] {child_path} content:\n{file_r.content}{CLI_CLR}")
                        continue
                    docs_content_parts.append(
                        f"--- {child_path} ---\n[FILE TOO LARGE FOR PRELOAD — use read or search to access directly]"
                    )
                    continue
                except Exception:
                    pass
                if "." not in entry.name:
                    _read_dir(child_path, seen)

        for dir_name in to_preload:
            _read_dir(f"/{dir_name}", set())

    # Step 4: fetch SQL schema + property key sample if /bin/sql exists
    sql_schema = ""
    sql_sample = ""
    if tree_result is not None:
        _has_bin = any(e.name == "bin" for e in tree_result.root.children)
        if _has_bin:
            print(f"{CLI_BLUE}[prephase] fetching SQL schema...{CLI_CLR}", end=" ")
            try:
                schema_result = vm.exec(ExecRequest(path="/bin/sql", args=[".schema"], stdin=""))
                sql_schema = schema_result.stdout.strip()
                print(f"{CLI_GREEN}ok ({len(sql_schema)} chars){CLI_CLR}")
            except Exception as e:
                print(f"{CLI_YELLOW}failed: {e}{CLI_CLR}")
            # Fetch distinct property keys so agent knows the exact key format (underscore vs space)
            print(f"{CLI_BLUE}[prephase] fetching property keys sample...{CLI_CLR}", end=" ")
            try:
                _key_q = "SELECT DISTINCT key FROM product_properties ORDER BY key"
                key_result = vm.exec(ExecRequest(path="/bin/sql", args=[_key_q], stdin=""))
                sql_sample = key_result.stdout.strip()
                print(f"{CLI_GREEN}ok{CLI_CLR}")
            except Exception as e:
                print(f"{CLI_YELLOW}failed: {e}{CLI_CLR}")

    # Step 5: context()
    print(f"{CLI_BLUE}[prephase] context...{CLI_CLR}", end=" ")
    ctx_content = ""
    try:
        ctx_result = vm.context(ContextRequest())
        ctx_content = (ctx_result.content or "").strip()
        if ctx_content:
            print(f"{CLI_GREEN}ok ({len(ctx_content)} chars){CLI_CLR}")
        else:
            print(f"{CLI_YELLOW}not available: content{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}not available: {e}{CLI_CLR}")

    # Build user context message
    parts = [f"TASK: {task_text}", f"VAULT STRUCTURE:\n{tree_txt}"]
    if agents_md_content:
        if _LOG_LEVEL == "DEBUG":
            print(f"{CLI_BLUE}[prephase] AGENTS.MD content:\n{agents_md_content}{CLI_CLR}")
        parts.append(f"\n{agents_md_path} CONTENT (source of truth for vault semantics):\n{agents_md_content}")
    if docs_content_parts:
        parts.append("\nDOCS/ CONTENT (workflow rules — follow these exactly):\n" + "\n\n".join(docs_content_parts))
    if sql_schema:
        parts.append(f"\nSQL SCHEMA (use with /bin/sql):\n{sql_schema}")
    if sql_sample:
        parts.append(f"\nPRODUCT PROPERTY KEYS (use exact key names in WHERE clauses):\n{sql_sample}")
    if ctx_content:
        parts.append(f"\nTASK CONTEXT:\n{ctx_content}")
    parts.append(
        "\nNOTE: Use the vault structure and AGENTS.MD above to identify actual folder paths."
    )

    log.append({"role": "user", "content": "\n".join(parts)})
    preserve_prefix = list(log)

    print(f"{CLI_BLUE}[prephase] done{CLI_CLR}")

    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
    )
