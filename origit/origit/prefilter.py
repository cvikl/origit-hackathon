"""Deterministic ASI pre-filter — decides whether a push needs Bob's review.

Runs on every push in the console (and locally via ``origit prefilter``). Costs zero Bobcoins.
Bob is only asked to write ASI evidence when at least one trigger fires.

Triggers (each returns a Finding {asi, severity, cwe, evidence, ref}):
  * new dependency present (added_deps non-empty)              -> ASI04 low, CWE-829
  * dependency added without reading its docs                  -> ASI04 medium, CWE-829
  * external read present (read.kind in url|mcp)                -> ASI01 informational, CWE-829
  * commands executed are part of the record, not a finding; a command matching a code-execution
    pattern (fetch piped to a shell, eval, base64 decode to shell, chmod +x, curl|wget to a non-local host) -> ASI05 medium, CWE-94
  * agent config changed (.bob/, CLAUDE.md, AGENTS.md, rules, skills)
      by a human                                                  -> ASI06 informational (audit trail), CWE-829
      by the agent itself                                         -> ASI06 medium, CWE-829
  * new instructions inside a changed agent-config file (insider or agent): hidden characters,
    override phrases ("ignore previous instructions", "do not tell the user"), fetch-and-run commands -> ASI01 high, CWE-506/CWE-829
  * invisible / bidi characters in anything the agent read      -> ASI01 high, CWE-506
      Unicode tag block  [\\U000E0000-\\U000E007F]  (decoded and quoted as evidence)
      zero-width         U+200B U+200C U+200D U+2060 U+FEFF
      bidi overrides     U+202A-U+202E U+2066-U+2069
  * secrets/env touched (.env, *.pem, id_rsa, *.key)            -> ASI03 medium, CWE-200

Severity labels are CVSS-style hints for the console; Bob's evidence may raise or lower them.
The security teammate owns the rule list; keep each rule a small pure function so it is unit-testable.
"""

from __future__ import annotations

import re
from typing import Any

UNICODE_TAG_RE = re.compile(r"[\U000E0000-\U000E007F]")
INVISIBLE_RE = re.compile(r"[​‌‍⁠﻿]")
BIDI_RE = re.compile(r"[‪-‮⁦-⁩]")

AGENT_CONFIG_RE = re.compile(r"(^|/)(\.bob/|\.bobrules|CLAUDE\.md$|AGENTS\.md$|\.cursorrules$|\.claude/|skills?/)")
SECRET_PATH_RE = re.compile(r"(^|/)(\.env(\..*)?$|.*\.pem$|id_rsa|.*\.key$|secrets?\.(json|ya?ml)$)")

CWE = {
    "CWE-506": "Embedded Malicious Code",
    "CWE-829": "Inclusion of Functionality from Untrusted Control Sphere",
    "CWE-94": "Improper Control of Generation of Code (Code Injection)",
    "CWE-200": "Exposure of Sensitive Information to an Unauthorized Actor",
}

ASI = {
    "ASI01": "Agent Goal Hijack",
    "ASI02": "Tool Misuse and Exploitation",
    "ASI03": "Identity and Privilege Abuse",
    "ASI04": "Agentic Supply Chain Vulnerabilities",
    "ASI05": "Unexpected Code Execution (RCE)",
    "ASI06": "Memory and Context Poisoning",
    "ASI07": "Insecure Inter-Agent Communication",
    "ASI08": "Cascading Failures",
    "ASI09": "Human-Agent Trust Exploitation",
    "ASI10": "Rogue Agents",
}

SEVERITIES = ("informational", "low", "medium", "high", "critical")


def has_hidden_text(text: str) -> dict[str, int]:
    """Count invisible / smuggling characters in text. Empty dict == clean."""
    out = {}
    for name, rx in (("unicode_tag", UNICODE_TAG_RE), ("zero_width", INVISIBLE_RE), ("bidi", BIDI_RE)):
        n = len(rx.findall(text))
        if n:
            out[name] = n
    return out


def decode_unicode_tags(text: str) -> str:
    """Reveal a Unicode-tag smuggled string (U+E0020..E007E map to ASCII 0x20..0x7E)."""
    return "".join(chr(ord(c) - 0xE0000) for c in UNICODE_TAG_RE.findall(text) if 0xE0020 <= ord(c) <= 0xE007E)


def _f(asi: str, severity: str, cwe: str, evidence: str, ref: str | None = None) -> dict[str, Any]:
    return {"asi": asi, "title": ASI[asi], "severity": severity, "cwe": cwe, "evidence": evidence, "ref": ref}


def rule_new_dependency(record: dict[str, Any], *_: Any) -> list[dict[str, Any]]:
    return [
        _f("ASI04", "low", "CWE-829", f"agent added dependency {d['name']}@{d.get('version')} ({d.get('registry', 'npm')})", f"{d['name']}@{d.get('version')}")
        for d in record.get("added_deps", [])
    ]


def rule_external_read(record: dict[str, Any], *_: Any) -> list[dict[str, Any]]:
    return [
        _f("ASI01", "informational", "CWE-829", f"agent read external content via {r['kind']}: {r['ref']}", r["ref"])
        for r in record.get("read", []) if r.get("kind") in ("url", "mcp")
    ]


DANGEROUS_CMD_RE = re.compile(
    r"(curl|wget)[^|\n]*\|\s*(ba|z|k|da)?sh\b"          # fetch piped to a shell
    r"|\beval\b"
    r"|base64\s+(-d|--decode)[^|\n]*\|\s*(ba|z|k|da)?sh\b"
    r"|\bchmod\s+\+x\b"
    r"|\brm\s+-rf?\s+/(\s|$)"                             # destructive: wipe from root
    r"|\b(curl|wget)\b(?![^\n]*(localhost|127\.0\.0\.1))[^\n]*https?://",  # network fetch to a non-local host
    re.I,
)
OVERRIDE_RE = re.compile(
    r"ignore (all )?(previous|prior|above|earlier) instructions|do not (tell|inform|mention to) the (user|human)|"
    r"without (telling|informing) the (user|human)|(curl|wget)[^\n]*\|\s*(ba|z)?sh\b|exfiltrat|send .{0,40}(env|secrets?|credentials?) to",
    re.I,
)


def rule_commands(record: dict[str, Any], *_: Any) -> list[dict[str, Any]]:
    """Commands are evidence in the record (``commands[]``), not a finding by themselves. Only a command that looks like
    code execution from untrusted input is flagged (ASI05 medium). Test runs, installs and file edits stay silent."""
    return [
        _f("ASI05", "medium", "CWE-94", f"command matches a code-execution pattern: {c.strip()[:160]}", c.strip()[:80])
        for c in record.get("commands", []) if DANGEROUS_CMD_RE.search(c)
    ]


def rule_agent_config_changed(record: dict[str, Any], changed_files: list[str], *_: Any) -> list[dict[str, Any]]:
    """Changes to what the agent obeys are always recorded. A human maintaining the config is an audit-trail entry
    (informational); an agent rewriting its own instructions is ASI06 medium."""
    human = record.get("actor", {}).get("kind") == "human"
    who = "human" if human else "the agent itself"
    return [
        _f("ASI06", "informational" if human else "medium", "CWE-829", f"agent configuration changed by {who}: {p}", p)
        for p in changed_files if AGENT_CONFIG_RE.search(p)
    ]


def rule_config_instructions(record: dict[str, Any], changed_files: list[str], read_texts: dict[str, str], changed_texts: dict[str, str] | None = None, *_: Any) -> list[dict[str, Any]]:
    """New instructions inside a changed agent-config file — the malicious-insider (or self-modifying agent) case.
    Needs the content of the changed files (``changed_texts``: path -> text after the change)."""
    out = []
    for p, text in (changed_texts or {}).items():
        if not AGENT_CONFIG_RE.search(p) or not text:
            continue
        hidden = has_hidden_text(text)
        if hidden:
            decoded = decode_unicode_tags(text)
            ev = f"hidden characters in agent configuration ({', '.join(f'{k}={v}' for k, v in hidden.items())})"
            if decoded:
                ev += f'; decoded: "{decoded[:200]}"'
            out.append(_f("ASI01", "high", "CWE-506", ev, p))
        m = OVERRIDE_RE.search(text)
        if m:
            line = next((l.strip() for l in text.splitlines() if m.group(0) in l), m.group(0))
            out.append(_f("ASI01", "high", "CWE-829", f'instruction in agent configuration that overrides or hides behaviour: "{line[:200]}"', p))
    return out


def rule_hidden_text(record: dict[str, Any], changed_files: list[str], read_texts: dict[str, str], *_: Any) -> list[dict[str, Any]]:
    out = []
    for ref, text in read_texts.items():
        hidden = has_hidden_text(text)
        if not hidden:
            continue
        decoded = decode_unicode_tags(text)
        ev = f"invisible characters in content the agent read ({', '.join(f'{k}={v}' for k, v in hidden.items())})"
        if decoded:
            ev += f'; decoded Unicode-tag text: "{decoded[:300]}"'
        out.append(_f("ASI01", "high", "CWE-506", ev, ref))
    return out


def rule_secrets_touched(record: dict[str, Any], changed_files: list[str], *_: Any) -> list[dict[str, Any]]:
    paths = [r["ref"] for r in record.get("read", []) if r.get("kind") == "file"] + list(record.get("wrote", [])) + list(changed_files)
    return [_f("ASI03", "medium", "CWE-200", f"secret or credential file touched: {p}", p) for p in sorted(set(paths)) if SECRET_PATH_RE.search(p)]



def rule_dependency_not_read(record: dict[str, Any], *_: Any) -> list[dict[str, Any]]:
    """ASI04 medium — agent added a dependency without reading any of its documentation.

    Suppressed when the dep name appears in any read ref of kind ``file``
    (e.g. node_modules/<name>/README.md) or kind ``url``.
    """
    read_refs = [r["ref"] for r in record.get("read", []) if r.get("kind") in ("file", "url")]
    out = []
    for d in record.get("added_deps", []):
        name = d["name"]
        if not any(name in ref for ref in read_refs):
            out.append(_f(
                "ASI04", "medium", "CWE-829",
                f"agent added dependency {name}@{d.get('version')} without reading its documentation",
                f"{name}@{d.get('version')}",
            ))
    return out

RULES = [rule_new_dependency, rule_external_read, rule_commands, rule_agent_config_changed, rule_config_instructions, rule_hidden_text, rule_secrets_touched, rule_dependency_not_read]


def run(record: dict[str, Any], changed_files: list[str] | None = None, read_texts: dict[str, str] | None = None,
        changed_texts: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Apply every rule. ``changed_texts`` (path -> content after the commit) enables the config-instruction rule.
    Returns findings sorted by severity (highest first) then ASI code."""
    changed_files = changed_files or []
    read_texts = read_texts or {}
    findings = [f for rule in RULES for f in rule(record, changed_files, read_texts, changed_texts or {})]
    findings.sort(key=lambda f: (-SEVERITIES.index(f["severity"]), f["asi"]))
    return findings


def needs_review(findings: list[dict[str, Any]]) -> bool:
    """Bob is asked to write evidence only when something fired."""
    return bool(findings)
