#!/usr/bin/env python3
"""
Privacy check: block personal portfolio data from reaching this public repo.

Runs as a git pre-commit hook (.githooks/pre-commit) on the lines a commit adds,
or on demand across every tracked file.

This file is public, so it holds no personal terms itself. At run time it reads them
from gitignored local files:
  - portfolio/accounts/*.md: account IDs, cash and total values, position quantities
    (matched together with their ticker), cost-basis prices
  - portfolio/private-terms.txt (optional): extra words to block, one per line,
    e.g. an employer name. Lines starting with # are comments.
Plus a few generic patterns (fractional share counts, account numbers).
In a clone without portfolio/ (e.g. cloud sessions) only the generic patterns run.

Usage:
    .venv/bin/python3 scripts/privacy-check.py            # staged changes (what the hook runs)
    .venv/bin/python3 scripts/privacy-check.py --all      # every tracked file
Add "privacy-ok" anywhere on a line to allow it (e.g. a hypothetical example that
happens to match). Exit code 1 when anything is found.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACCOUNTS_DIR = ROOT / "portfolio" / "accounts"
TERMS_FILE = ROOT / "portfolio" / "private-terms.txt"
SKIP_PREFIXES = ("research/", "portfolio/")
SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".lock")

GENERIC = [
    (re.compile(r"\b\d+\.\d{2,4}\s*(?:sh|shares)\b", re.IGNORECASE), "fractional share count"),
    (re.compile(r"account[_ ]?(?:id|number|no\.?|#)\s*[:=#]?\s*[A-Z]?\d{6,}", re.IGNORECASE), "account number"),
]


def number_pattern(value: str) -> str:
    """Regex for a number written with or without thousands commas, as a whole token."""
    digits, _, frac = value.replace(",", "").partition(".")
    if len(digits) > 3:
        head, rest = digits[: len(digits) % 3 or 3], digits[len(digits) % 3 or 3:]
        groups = [head] + [rest[i:i + 3] for i in range(0, len(rest), 3)]
        int_part = ",?".join(groups)
    else:
        int_part = digits
    body = int_part + (r"\." + frac if frac else "")
    return r"(?<![\d.,])" + body + r"(?![\d]|[.,]\d)"


def load_private_terms() -> list:
    """Build (regex, label, ticker_or_None) rules from the local portfolio files."""
    rules = []
    if TERMS_FILE.exists():
        for line in TERMS_FILE.read_text().splitlines():
            term = line.strip()
            if term and not term.startswith("#"):
                rules.append((re.compile(r"\b" + re.escape(term) + r"\b"), "private term", None))

    for f in sorted(ACCOUNTS_DIR.glob("*.md")) if ACCOUNTS_DIR.exists() else []:
        text = f.read_text()
        fm = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if fm:
            for key in ("account_id", "total_value", "cash"):
                m = re.search(rf"^{key}:\s*\"?([\d,]+(?:\.\d+)?)", fm.group(1), re.MULTILINE)
                if m and len(m.group(1).replace(",", "").split(".")[0]) >= 4:
                    rules.append((re.compile(number_pattern(m.group(1))), f"{f.stem} {key}", None))

        for line in text.splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip().strip("*") for c in line.strip("|").split("|")]
            if len(cells) < 3 or not re.fullmatch(r"[A-Z]{1,5}", cells[0]):
                continue
            ticker = cells[0]
            qty = cells[1].replace(",", "")
            if re.fullmatch(r"\d+(?:\.\d+)?", qty):
                q = float(qty)
                # Small or round quantities are too common in hypothetical examples.
                if q >= 10 and q % 10 != 0:
                    rules.append((re.compile(number_pattern(cells[1]) + r"(?!\s*%)"), f"{ticker} quantity", ticker))
            cost = re.fullmatch(r"\$([\d,]+\.\d{2})", cells[2])
            if cost:
                rules.append((re.compile(r"\$?" + number_pattern(cost.group(1))), f"{ticker} cost basis", None))
    return rules


def staged_lines() -> list:
    """(path, line_no, text) for every line added in the staged diff."""
    out = subprocess.run(["git", "diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    lines, path, line_no = [], None, 0
    for raw in out.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path:
            lines.append((path, line_no, raw[1:]))
            line_no += 1
    return lines


def tracked_lines() -> list:
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.splitlines()
    lines = []
    for path in files:
        p = ROOT / path
        if not p.is_file():
            continue
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        lines.extend((path, i, t) for i, t in enumerate(text.splitlines(), 1))
    return lines


def scan(lines: list, rules: list) -> list:
    findings = []
    for path, line_no, text in lines:
        if path.startswith(SKIP_PREFIXES) or path.endswith(SKIP_SUFFIXES) or "privacy-ok" in text:
            continue
        for regex, label in GENERIC:
            if regex.search(text):
                findings.append((path, line_no, label, text))
        for regex, label, ticker in rules:
            if ticker and not re.search(rf"\b{ticker}\b", text):
                continue
            if regex.search(text):
                findings.append((path, line_no, label, text))
    return findings


def main():
    parser = argparse.ArgumentParser(description="Block personal portfolio data from the public repo")
    parser.add_argument("--all", action="store_true", help="Scan every tracked file, not just staged changes")
    args = parser.parse_args()

    rules = load_private_terms()
    lines = tracked_lines() if args.all else staged_lines()
    findings = scan(lines, rules)

    if not findings:
        scope = "tracked files" if args.all else "staged changes"
        print(f"privacy-check: OK ({len(lines)} lines in {scope}, {len(rules)} private terms)")
        return

    print("privacy-check: possible personal data in a public file:\n", file=sys.stderr)
    for path, line_no, label, text in findings:
        snippet = text.strip()
        snippet = snippet[:110] + ("…" if len(snippet) > 110 else "")
        print(f"  {path}:{line_no}  [{label}]  {snippet}", file=sys.stderr)
    print("\nRemove it or swap in hypothetical round numbers. If a line is a false positive, add "
          "'privacy-ok' to it.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
