import os
import re
from dataclasses import dataclass, field

from bitgn.vm.pcm_connect import PcmRuntimeClientSync
from bitgn.vm.pcm_pb2 import ContextRequest, ListRequest, ReadRequest, TreeRequest

from .dispatch import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

_AGENTS_MD_BUDGET = 8000  # FIX-209: increased from 2500; full AGENTS.MD eliminates non-determinism (audit 3.3)


def _filter_agents_md(content: str, task_text: str) -> tuple[str, bool]:
    """Include full AGENTS.MD up to budget; deterministic truncation if over.

    Previous word-overlap heuristic removed — it caused non-deterministic section
    selection based on task phrasing (audit 3.3).
    """
    if len(content) <= _AGENTS_MD_BUDGET:
        return content, False
    return content[:_AGENTS_MD_BUDGET] + f"\n[...truncated — full AGENTS.MD is {len(content)} chars]", True


@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list  # messages to never compact
    agents_md_content: str = ""  # content of AGENTS.md if found
    agents_md_path: str = ""  # path where AGENTS.md was found
    # Inbox files loaded during prephase: list of (path, content) sorted alphabetically.
    # Used by _run_pre_route for preloop injection check before the main loop starts.
    inbox_files: list = field(default_factory=list)
    # Vault tree text from step 1 — passed to prompt_builder for task-specific guidance.
    vault_tree_text: str = ""


def _format_tree_entry(entry, prefix: str = "", is_last: bool = True) -> list[str]:
    branch = "└── " if is_last else "├── "
    lines = [f"{prefix}{branch}{entry.name}"]
    child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
    children = list(entry.children)
    for idx, child in enumerate(children):
        lines.extend(_format_tree_entry(child, prefix=child_prefix, is_last=idx == len(children) - 1))
    return lines


def _render_tree_result(result, root_path: str = "/", level: int = 2) -> str:
    """Render TreeResponse into compact shell-like output."""
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


# Few-shot user→assistant pair — strongest signal for JSON-only output.
# Placed immediately after system prompt so the model sees its own expected format
# before any task context. More reliable than response_format for Ollama-proxied
# cloud models that ignore json_object enforcement.
# NOTE: generic path used intentionally — discovery-first principle (no vault-specific hardcoding).
_FEW_SHOT_USER = "Example: what files are in the notes folder?"
_FEW_SHOT_ASSISTANT = (
    '{"current_state":"listing notes folder to identify files",'
    '"plan_remaining_steps_brief":["list /notes","act on result"],'
    '"task_completed":false,'
    '"function":{"tool":"list","path":"/notes"}}'
)


def run_prephase(
    vm: PcmRuntimeClientSync,
    task_text: str,
    system_prompt_text: str,
) -> PrephaseResult:
    """Build the initial conversation log before the main agent loop.

    Steps performed:
    1. tree -L 2 / — captures top-level vault layout so the agent knows folder names upfront.
    2. Read AGENTS.MD — source of truth for vault semantics and folder roles.
    3. Auto-preload directories referenced in AGENTS.MD: extracts top-level dir names from
       the tree, intersects with dirs mentioned in AGENTS.MD, then recursively reads all
       non-template files from those dirs. No folder names are hardcoded — the intersection
       logic works for any vault layout.
    4. context() — task-level metadata injected by the harness (e.g. current date, user info).

    The resulting log and preserve_prefix are passed directly to run_loop(). The
    preserve_prefix is never compacted, so vault structure and AGENTS.MD remain visible
    throughout the entire task execution.
    """
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

    log: list = [
        {"role": "system", "content": system_prompt_text},
        {"role": "user", "content": _FEW_SHOT_USER},
        {"role": "assistant", "content": _FEW_SHOT_ASSISTANT},
    ]

    # Step 1: tree "/" -L 2 — gives the agent the top-level vault layout upfront
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

    # Step 2: read AGENTS.MD — source of truth for vault semantics and folder roles.
    # Discovery-first: check standard root paths, then scan first-level dirs from tree.
    # No vault-specific paths hardcoded — works for any vault layout.
    agents_md_content = ""
    agents_md_path = ""
    # Standard candidates (root-level, case variants)
    _agents_md_standard = ["/AGENTS.MD", "/AGENTS.md"]
    # Dynamic candidates: first-level directories from tree (e.g. /docs/AGENTS.md, /02_notes/AGENTS.md)
    _agents_md_dynamic: list[str] = []
    if tree_result is not None:
        for _entry in tree_result.root.children:
            if _entry.children:  # directory
                for _variant in ("AGENTS.MD", "AGENTS.md"):
                    _agents_md_dynamic.append(f"/{_entry.name}/{_variant}")
    for candidate in _agents_md_standard + _agents_md_dynamic:
        try:
            r = vm.read(ReadRequest(path=candidate))
            if r.content:
                agents_md_content = r.content
                agents_md_path = candidate
                print(f"{CLI_BLUE}[prephase] read {candidate}:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
                break
        except Exception:
            pass

    # Step 2.5: auto-preload directories referenced in AGENTS.MD
    # Algorithm:
    #   1. Extract top-level directory names from the tree result
    #   2. Extract directory names mentioned in AGENTS.MD (backtick or plain `name/` patterns)
    #   3. Intersection → list + read each file in those dirs (skip templates/README)
    # No hardcoded folder names — works for any vault layout.
    docs_content_parts: list[str] = []
    inbox_files: list[tuple[str, str]] = []
    if agents_md_content and tree_result is not None:
        # Top-level dirs from tree
        top_level_dirs = {entry.name for entry in tree_result.root.children if entry.children or True}
        # Dir names mentioned in AGENTS.MD: match `name/` or plain word/
        mentioned = set(re.findall(r'`?(\w[\w-]*)/`?', agents_md_content))
        # Intersect with actual dirs in vault
        to_preload = sorted(mentioned & top_level_dirs)
        # Skip dirs that are primary data stores — they are too large and agent reads selectively
        _skip_data_dirs = {"contacts", "accounts", "opportunities", "reminders", "my-invoices", "outbox", "inbox"}
        to_preload = [d for d in to_preload if d not in _skip_data_dirs]
        if to_preload:
            print(f"{CLI_BLUE}[prephase] referenced dirs to preload: {to_preload}{CLI_CLR}")
        # _read_dir: recursively reads all files from a directory path
        def _read_dir(dir_path: str, seen: set) -> None:
            try:
                entries = vm.list(ListRequest(name=dir_path))
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
                # Try to read as file first; if it fails with no content, treat as subdir
                try:
                    file_r = vm.read(ReadRequest(path=child_path))
                    if file_r.content:
                        _fc = file_r.content
                        # [FIX-133] PCM runtime may return partial content for large files.
                        # Warn agent to re-read for exact counts/enumerations.
                        if len(_fc) >= 500:
                            _fc += (
                                f"\n[PREPHASE EXCERPT — content may be partial."
                                f" For exact counts or full content use: read('{child_path}')]"
                            )
                        docs_content_parts.append(f"--- {child_path} ---\n{_fc}")
                        # Collect raw content for inbox dirs — used for preloop injection check
                        if "inbox" in dir_path.lower():
                            inbox_files.append((child_path, file_r.content))
                        print(f"{CLI_BLUE}[prephase] read {child_path}:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
                        if _LOG_LEVEL == "DEBUG":
                            print(f"{CLI_BLUE}[prephase] {child_path} content:\n{file_r.content}{CLI_CLR}")
                        continue
                    # [FIX-244] Empty content = file too large for preload read.
                    # Do NOT fall through to _read_dir — that would try to list the file as a
                    # directory and produce a confusing "path must reference a folder" error.
                    # Instead, annotate so the agent knows to read directly.
                    docs_content_parts.append(
                        f"--- {child_path} ---\n"
                        f"[FILE TOO LARGE FOR PRELOAD — use read or search to access this file directly]"
                    )
                    print(f"{CLI_YELLOW}[prephase] {child_path}: empty content (too large), annotated{CLI_CLR}")
                    continue
                except Exception:
                    pass
                # [FIX-244] Exception on read (e.g. timeout for large files) —
                # if entry has a file extension it's a file, not a directory.
                # Annotate as unreadable; do NOT recurse (_read_dir would
                # call vm.list on a file path and log "path must reference a folder").
                if "." in entry.name:
                    # FIX-285: retry once on read timeout before annotating as unreadable
                    import time as _time
                    _time.sleep(0.5)
                    try:
                        _retry_r = vm.read(ReadRequest(path=child_path))
                        if _retry_r.content:
                            _rc = _retry_r.content
                            if len(_rc) >= 500:
                                _rc += (
                                    f"\n[PREPHASE EXCERPT — content may be partial."
                                    f" For exact counts or full content use: read('{child_path}')]"
                                )
                            docs_content_parts.append(f"--- {child_path} ---\n{_rc}")
                            if "inbox" in dir_path.lower():
                                inbox_files.append((child_path, _retry_r.content))
                            print(f"{CLI_BLUE}[prephase] read {child_path}:{CLI_CLR} {CLI_GREEN}ok (retry){CLI_CLR}")
                            if _LOG_LEVEL == "DEBUG":
                                print(f"{CLI_BLUE}[prephase] {child_path} content:\n{_retry_r.content}{CLI_CLR}")
                            continue
                    except Exception:
                        pass
                    docs_content_parts.append(
                        f"--- {child_path} ---\n"
                        f"[FILE UNREADABLE (read error/timeout) — use search to find content]"
                    )
                    print(f"{CLI_YELLOW}[prephase] {child_path}: read error (timeout?), annotated{CLI_CLR}")
                    continue
                # No file extension → treat as subdirectory, recurse
                _read_dir(child_path, seen)

        for dir_name in to_preload:
            _read_dir(f"/{dir_name}", set())

    # Estimate VAULT_DATE from date-prefixed filenames.
    # Priority: inbox file paths (represent "today's" messages) > tree-wide mode.
    _date_prefix_re = re.compile(r'\b(\d{4}-\d{2}-\d{2})__')
    _vault_date_hint = ""
    _vault_date_src = ""
    # First: dates from inbox file paths (most reliable — inbox = arriving messages)
    _inbox_dates = sorted({
        m.group(1) for p, _ in inbox_files
        if (m := _date_prefix_re.search(p))
    })
    if _inbox_dates:
        _vault_date_est = _inbox_dates[len(_inbox_dates) // 2]  # median
        _vault_date_src = "inbox filenames"
    else:
        # Fallback: mode of all date-prefixed files in tree (excludes far-future outliers on average)
        _found_dates = _date_prefix_re.findall(tree_txt)
        if _found_dates:
            _date_counts: dict[str, int] = {}
            for _d in _found_dates:
                _date_counts[_d] = _date_counts.get(_d, 0) + 1
            _vault_date_est = max(_date_counts, key=lambda k: _date_counts[k])
            _vault_date_src = "tree date-prefixes"
        else:
            _vault_date_est = ""
    # FIX-326: second fallback — if no date-prefixed filenames exist (flat vault
    # like CRM: accounts/, reminders/, opportunities/), sample 3 JSON records per
    # folder in priority order and take max ISO date from field values.
    # Max(last_contacted_on, due_on, next_follow_up_on) ≈ VAULT_DATE "today".
    if not _vault_date_est:
        _iso_re = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
        _top_names = {e.name for e in tree_result.root.children} if tree_result is not None else set()
        for _probe_dir in ("reminders", "accounts", "opportunities"):
            if _probe_dir not in _top_names:
                continue
            try:
                _entries = vm.list(ListRequest(name=f"/{_probe_dir}"))
            except Exception:
                continue
            _sample_dates: list[str] = []
            _sampled = 0
            for _entry in _entries.entries:
                if _sampled >= 3:
                    break
                if _entry.name.upper() == "README.MD" or not _entry.name.endswith(".json"):
                    continue
                try:
                    _r = vm.read(ReadRequest(path=f"/{_probe_dir}/{_entry.name}"))
                    if _r.content:
                        _sample_dates.extend(_iso_re.findall(_r.content))
                        _sampled += 1
                except Exception:
                    continue
            if _sample_dates:
                _vault_date_est = max(_sample_dates)
                _vault_date_src = f"/{_probe_dir} max ISO date"
                break

    if _vault_date_est:
        _vault_date_hint = f"VAULT_DATE: {_vault_date_est}  (estimated — verify against account `last_contacted_on` for temporal queries)"
        print(f"{CLI_BLUE}[prephase] vault_date estimated: {_vault_date_est} (source: {_vault_date_src}){CLI_CLR}")

    # Inject vault layout + AGENTS.MD as context — the agent reads this to discover
    # where "cards", "threads", "inbox", etc. actually live in the vault.
    prephase_parts = [f"TASK: {task_text}", f"VAULT STRUCTURE:\n{tree_txt}"]
    if _vault_date_hint:
        prephase_parts.append(_vault_date_hint)
    if agents_md_content:
        agents_md_injected, was_filtered = _filter_agents_md(agents_md_content, task_text)
        if was_filtered:
            print(f"{CLI_YELLOW}[prephase] AGENTS.MD filtered: {len(agents_md_content)} → {len(agents_md_injected)} chars{CLI_CLR}")
        if _LOG_LEVEL == "DEBUG":
            print(f"{CLI_BLUE}[prephase] AGENTS.MD content:\n{agents_md_content}{CLI_CLR}")
        prephase_parts.append(
            f"\n{agents_md_path} CONTENT (source of truth for vault semantics):\n{agents_md_injected}"
        )
    if docs_content_parts:
        prephase_parts.append(
            "\nDOCS/ CONTENT (workflow rules — follow these exactly):\n" + "\n\n".join(docs_content_parts)
        )
    prephase_parts.append(
        "\nNOTE: Use the vault structure and AGENTS.MD above to identify actual folder "
        "paths. Verify paths with list/find before acting. Do not assume paths."
    )

    log.append({"role": "user", "content": "\n".join(prephase_parts)})


    # Step 3: context — task-level metadata from the harness.
    # FIX-328: log content fully so we can audit what the harness injects
    # (e.g. submission-specific dates). ContextResponse currently has only
    # `content: string`; if that expands to include structured metadata in
    # the proto schema, dump all non-empty fields here.
    print(f"{CLI_BLUE}[prephase] context...{CLI_CLR}", end=" ")
    try:
        ctx_result = vm.context(ContextRequest())
        ctx_content = (ctx_result.content or "").strip()
        if ctx_content:
            log.append({"role": "user", "content": f"TASK CONTEXT:\n{ctx_content}"})
            print(f"{CLI_GREEN}ok ({len(ctx_content)} chars){CLI_CLR}")
            if _LOG_LEVEL == "DEBUG":
                print(f"{CLI_BLUE}[prephase] context content:\n{ctx_content}{CLI_CLR}")
        else:
            print(f"{CLI_YELLOW}empty (no harness-provided metadata){CLI_CLR}")
        # Surface any extra proto fields added by the benchmark (future-proofing).
        for _f in ctx_result.DESCRIPTOR.fields:
            if _f.name == "content":
                continue
            _v = getattr(ctx_result, _f.name, None)
            if _v:
                print(f"{CLI_BLUE}[prephase] context.{_f.name}: {_v!r}{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}not available: {e}{CLI_CLR}")

    # preserve_prefix: always kept during log compaction
    preserve_prefix = list(log)

    print(f"{CLI_BLUE}[prephase] done{CLI_CLR}")

    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        inbox_files=sorted(inbox_files, key=lambda x: x[0]),
        vault_tree_text=tree_txt,
    )
