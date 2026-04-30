"""Security gate constants and functions for the agent loop.

Extracted from loop.py to reduce God Object size.
Covers FIX-203 (injection normalization), FIX-206 (contamination),
FIX-214 (format gate), FIX-215 (inbox injection), FIX-250 (write scope).

Public API used by loop.py:
  _normalize_for_injection() — FIX-203: leet/zero-width/NFKC normalization
  _CONTAM_PATTERNS           — FIX-206: anti-contamination regexes for email body
  _FORMAT_GATE_RE            — FIX-214: inbox From:/Channel: header check
  _INBOX_INJECTION_PATTERNS  — FIX-215, FIX-281: injection pattern list
  _INBOX_ACTION_RE           — FIX-215: action verb detection
  _check_write_scope()       — FIX-250: mutation path guard (system/email scope)
"""
import re
import unicodedata

from .classifier import TASK_INBOX, TASK_EMAIL, TASK_QUEUE


# ---------------------------------------------------------------------------
# FIX-203: Text normalization for injection detection
# ---------------------------------------------------------------------------

# Strips zero-width chars, NFKC-normalizes unicode (homoglyphs → ASCII),
# and replaces common leet substitutions before injection regex matching.
_LEET_MAP = str.maketrans("01345@", "oleasa")  # 0→o, 1→l, 3→e, 4→a, 5→s, @→a
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")


def _normalize_for_injection(text: str) -> str:
    """FIX-203: Normalize text before injection regex check."""
    t = _ZERO_WIDTH_RE.sub("", text)
    t = unicodedata.normalize("NFKC", t)
    t = t.translate(_LEET_MAP)
    return t


# Module-level regex for fast-path injection detection (compiled once, not per-task)
_INJECTION_RE = re.compile(
    r"ignore\s+(previous|above|prior)\s+instructions?"
    r"|disregard\s+(all|your|previous)"
    r"|new\s+(task|instruction)\s*:"
    r"|system\s*prompt\s*:"
    r'|"tool"\s*:\s*"report_completion"'
    # FIX-329: bridge-relay injection (t09-style)
    r"|security\s+relay\s*:\s*authenticated"
    r"|mirrored\s+through\s+(an\s+)?internal\s+bridge"
    r"|trusted\s+operational\s+guidance",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# FIX-206: Body anti-contamination patterns for outbox email verification
# ---------------------------------------------------------------------------

# Detects vault paths, tree output, tool results, and system file references
# leaked into email body.
_CONTAM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/[a-zA-Z_\-]+/", re.MULTILINE), "vault path"),
    (re.compile(r"VAULT STRUCTURE:"), "vault tree"),
    (re.compile(r"[├└│]──"), "tree output"),
    (re.compile(r"\bResult of Req_"), "tool result"),
    (re.compile(r"\bAGENTS\.MD\b"), "system file ref"),
]

# ---------------------------------------------------------------------------
# FIX-214: Format gate — inbox message must have From: or Channel: header
# ---------------------------------------------------------------------------

_FORMAT_GATE_RE = re.compile(r"^\s*(from|channel)\s*:", re.IGNORECASE | re.MULTILINE)

# ---------------------------------------------------------------------------
# FIX-215: Inbox injection patterns — code-level security check
# ---------------------------------------------------------------------------

_INBOX_INJECTION_PATTERNS = [
    re.compile(r"(read|list|open|check|inspect)\s+(docs/|AGENTS|otp\.txt)", re.IGNORECASE),
    re.compile(r"(override|escalat|jailbreak|bypass|system\s*override|forget\s*(your|the)\s*rules)", re.IGNORECASE),
    re.compile(r"(you\s+are\s+now|as\s+admin|special\s+authority)", re.IGNORECASE),
    re.compile(r"if\s+(char|otp|the\s+first)", re.IGNORECASE),
    # FIX-281: credential harvesting / exfiltration attempts
    re.compile(r"(collect|gather|send|transfer|exfiltrat)\s+.{0,40}(credential|password|secret|access.{0,10}(note|key|token))", re.IGNORECASE),
]
_INBOX_ACTION_RE = re.compile(r"\b(please\s+do|follow\s+this|run|execute)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# FIX-321: Write-payload injection patterns — detect embedded commands in content
# being written to the vault (e.g., capture snippets with injected tool notes).
# Distinct from _INBOX_INJECTION_PATTERNS which scan messages from external channels.
# ---------------------------------------------------------------------------

_WRITE_PAYLOAD_INJECTION_PATTERNS = [
    # "Embedded tool note:" — explicit command injection marker
    re.compile(r'^\s*Embedded\s+(tool|command|script)\s+(note|call|run|instruction)\s*:', re.IGNORECASE | re.MULTILINE),
    # Conditional imperative "if X => delete/remove/send/execute" embedded in content
    re.compile(r'\bif\s+[\w\s]{1,50}\s*=>\s*(remove|delete|send|execute|run|disable|drop)', re.IGNORECASE),
    # Authority-claiming metadata frontmatter typical of bridge/override injection
    re.compile(r'^origin\s*:\s*(security-bridge|admin|system-override|auth-bridge)', re.IGNORECASE | re.MULTILINE),
    # FIX-329: "Security relay / authenticated request" — bridge-injection header seen in t09
    re.compile(r'^\s*#?\s*Security\s+relay\s*:\s*authenticated', re.IGNORECASE | re.MULTILINE),
    re.compile(r'\bmirrored\s+through\s+(an\s+)?internal\s+bridge\b', re.IGNORECASE),
    re.compile(r'\btrusted\s+operational\s+guidance\b', re.IGNORECASE),
    re.compile(r'^\s*TRUSTED\s+PATCH\s*:', re.IGNORECASE | re.MULTILINE),
]

# FIX-415: vault policy files may use security terminology legitimately.
# Content read from these paths is exempt from write-payload injection scanning.
_TRUSTED_POLICY_PATHS = (
    "/docs/channels/",
    "/docs/process-",
    "/docs/automation.md",
    "/docs/task-completion.md",
    "/docs/inbox-",
)


def _check_write_payload_injection(content: str, source_path: str | None = None) -> bool:
    """FIX-321: Return True if write content contains embedded command injection.

    FIX-415: source_path from trusted policy paths (docs/channels/, docs/process-*, etc.)
    is exempt — channel registry and workflow docs legitimately use security terminology.
    """
    if source_path and any(source_path.startswith(p) for p in _TRUSTED_POLICY_PATHS):
        return False
    _norm = _normalize_for_injection(content)
    return any(p.search(_norm) for p in _WRITE_PAYLOAD_INJECTION_PATTERNS)


# ---------------------------------------------------------------------------
# FIX-377: Pasted-external-content injection markers
#
# Distinguishes the t09 case (pasted external content + embedded
# runtime_override / quoted-message asserting agent permissions / delimiter
# block claiming to override policy) from the t33 case (plain capture of a
# benign quoted excerpt attributed to an external site, no override markers).
# Used as a structural test for the wiki "Verified refusal: t09" pattern so
# that capture tasks like t33 are not falsely refused.
# ---------------------------------------------------------------------------

_PASTED_INJECTION_MARKERS = [
    # Override directives — runtime/system/policy override blocks.
    re.compile(r"\b(runtime|system|policy|security)_override\b", re.IGNORECASE),
    re.compile(r"\boverride\s*[:=]\s*(true|enabled|on|1)\b", re.IGNORECASE),
    # Authority-claiming permission directives commonly seen in t09's
    # quoted-message payload.
    re.compile(r"\b(export_contacts|share_thread|grant_access|disable_audit)\b", re.IGNORECASE),
    re.compile(r"\bconfirmation\s*=\s*not[-_]required\b", re.IGNORECASE),
    # Delimiter blocks claiming to be system/policy/jailbreak directives.
    re.compile(r"^\s*#{0,3}\s*(SYSTEM|POLICY|ADMIN|JAILBREAK|DEVELOPER)\s+(OVERRIDE|DIRECTIVE|MODE)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"<\s*(system|policy|admin)[-_]?override\s*>", re.IGNORECASE),
]


def _pasted_external_has_injection_markers(text: str) -> bool:
    """FIX-377: True iff pasted external content carries injection markers.

    A plain capture task that quotes a benign excerpt attributed to an
    external site (no override directives, no embedded permissions, no
    system blocks) returns False — it is NOT injection.
    """
    if not text:
        return False
    norm = _normalize_for_injection(text)
    if any(p.search(norm) for p in _PASTED_INJECTION_MARKERS):
        return True
    # Reuse write-payload markers (FIX-321/329): bridge/relay/trusted-patch
    # headers also count as injection markers when found in pasted content.
    return any(p.search(norm) for p in _WRITE_PAYLOAD_INJECTION_PATTERNS)


# ---------------------------------------------------------------------------
# FIX-250: Write-scope code enforcement (FIX-208)
# ---------------------------------------------------------------------------

_SYSTEM_PATH_PREFIXES = ("/docs/",)
_SYSTEM_PATHS_EXACT = frozenset({"/AGENTS.MD", "/AGENTS.md"})
_OTP_PATH = "/docs/channels/otp.txt"


def _check_write_scope(action, action_name: str, task_type: str) -> str | None:
    """Return error message if mutation violates write-scope, else None.

    Layer 1 (all types): deny system paths (docs/, AGENTS.MD).
      Exception: inbox + Req_Delete + otp.txt (OTP elevation).
    Layer 2 (email only): allow-list — only /outbox/ paths.
    """
    paths_to_check: list[str] = []
    if hasattr(action, "path") and action.path:
        paths_to_check.append(action.path)
    if hasattr(action, "from_name") and action.from_name:
        paths_to_check.append(action.from_name)
    if hasattr(action, "to_name") and action.to_name:
        paths_to_check.append(action.to_name)

    for p in paths_to_check:
        is_system = p in _SYSTEM_PATHS_EXACT or any(
            p.startswith(pfx) for pfx in _SYSTEM_PATH_PREFIXES
        )
        if is_system:
            # FIX-103: OTP deletion allowed for both inbox and queue task types
            if task_type in (TASK_INBOX, TASK_QUEUE) and action_name == "Req_Delete" and p == _OTP_PATH:
                continue
            return (
                f"Blocked: {action_name} targets system path '{p}'. "
                "System files (docs/, AGENTS.MD) are read-only. "
                "Choose a different target path."
            )
        if task_type == TASK_EMAIL and not p.startswith("/outbox/"):
            return (
                f"Blocked: {action_name} targets '{p}' but email tasks may only "
                "write to /outbox/. Use report_completion if no outbox write is needed."
            )

    return None
