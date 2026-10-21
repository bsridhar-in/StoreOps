"""Shared helpers for the harness scripts (paths, config, sprint-contract parsing, git)."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / ".harness"
OUTPUT = HARNESS / "output"
REVIEWS = HARNESS / "reviews"
RUBRIC_PATH = HARNESS / "skills" / "grading-criteria" / "rubric.json"

AC_ID = re.compile(r"\bAC-(\d+)\.(\d+)\b")
EMIT_LINE = re.compile(r"^\s*-\s*EMIT\s+`?(\w+)`?\s+from\s+`?(\w+)`?", re.MULTILINE)
HANDLE_LINE = re.compile(r"^\s*-\s*HANDLE\s+`?(\w+)`?\s+in\s+`?(\w+)`?", re.MULTILINE)
APPROVED_HEADING = "## Approved protected-file changes"


def load_json(path: Path) -> Any:  # noqa: ANN401 - arbitrary JSON
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:  # noqa: ANN401 - arbitrary JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def config() -> dict[str, Any]:
    data: dict[str, Any] = load_json(HARNESS / "config.json")
    return data


def rubric() -> dict[str, Any]:
    data: dict[str, Any] = load_json(RUBRIC_PATH)
    return data


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob (``*``, ``?``, ``**``) into an anchored regex on posix paths."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


def changed_files() -> list[str]:
    """Paths changed in the working tree relative to HEAD (staged, unstaged and untracked).

    The orchestrator commits after every PASS, so this is exactly the current sprint's diff.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        entry = line[3:]
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        paths.append(entry.strip().strip('"'))
    return sorted(set(paths))


@dataclass
class SprintContract:
    path: Path
    sprint: int
    ac_ids: list[str] = field(default_factory=list)
    emits: list[tuple[str, str]] = field(default_factory=list)
    handles: list[tuple[str, str]] = field(default_factory=list)
    approved_protected: list[str] = field(default_factory=list)


def contract_path(sprint: int) -> Path:
    return OUTPUT / f"sprint-{sprint}-contract.md"


def parse_contract(sprint: int) -> SprintContract | None:
    path = contract_path(sprint)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    ac_ids = sorted(
        {m.group(0) for m in AC_ID.finditer(text) if int(m.group(1)) == sprint},
        key=lambda ac: int(ac.split(".")[1]),
    )
    approved: list[str] = []
    if APPROVED_HEADING in text:
        section = text.split(APPROVED_HEADING, 1)[1].split("\n## ", 1)[0]
        for line in section.splitlines():
            item = line.strip()
            if item.startswith("- "):
                value = item[2:].strip().strip("`").split(" ", 1)[0].strip("`")
                if value and value.lower() not in {"none", "n/a"}:
                    approved.append(value)
    return SprintContract(
        path=path,
        sprint=sprint,
        ac_ids=ac_ids,
        emits=EMIT_LINE.findall(text),
        handles=HANDLE_LINE.findall(text),
        approved_protected=approved,
    )
