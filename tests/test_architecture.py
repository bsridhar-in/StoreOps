"""Static checks for the module boundary rules described in ``storeops.modules``."""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "storeops"
MODULES_DIR = SRC / "modules"
MODULES_PKG = "storeops.modules"

# module -> modules it may import (via their public package only)
ALLOWED_DEPENDENCIES: dict[str, set[str]] = {
    "staff": set(),
    "programmes": {"staff"},
    "activities": {"staff", "programmes"},
    "alerts": set(),  # event bus only
    "reports": set(),  # event bus only
}
# "users" (staff) is read-only for every other module.
STAFF_PUBLIC_READ_API = {"StaffReader", "StaffMember"}

BUILTIN_EXCEPTIONS = {
    name
    for name, obj in vars(builtins).items()
    if isinstance(obj, type) and issubclass(obj, BaseException)
}


@dataclass(frozen=True)
class ImportRef:
    file: Path
    module: str
    names: tuple[str, ...]


def module_names() -> list[str]:
    return sorted(p.name for p in MODULES_DIR.iterdir() if (p / "__init__.py").exists())


def imports_in(path: Path) -> list[ImportRef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    refs: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            refs.extend(ImportRef(path, alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module == MODULES_PKG:
                refs.extend(
                    ImportRef(path, f"{MODULES_PKG}.{alias.name}", ()) for alias in node.names
                )
            else:
                refs.append(ImportRef(path, node.module, tuple(a.name for a in node.names)))
    return refs


def cross_module_imports(module: str) -> list[ImportRef]:
    refs: list[ImportRef] = []
    for path in (MODULES_DIR / module).rglob("*.py"):
        for ref in imports_in(path):
            parts = ref.module.split(".")
            if ref.module.startswith(f"{MODULES_PKG}.") and parts[2] != module:
                refs.append(ref)
    return refs


def test_every_module_has_a_dependency_rule() -> None:
    assert module_names() == sorted(ALLOWED_DEPENDENCIES)


@pytest.mark.parametrize("module", sorted(ALLOWED_DEPENDENCIES))
def test_module_has_three_layers(module: str) -> None:
    for layer in ("routes.py", "service.py", "repository.py"):
        assert (MODULES_DIR / module / layer).is_file(), f"{module} is missing {layer}"


@pytest.mark.parametrize("module", sorted(ALLOWED_DEPENDENCIES))
def test_cross_module_imports_follow_rules(module: str) -> None:
    for ref in cross_module_imports(module):
        target = ref.module.split(".")[2]
        where = ref.file.relative_to(SRC)
        assert target in ALLOWED_DEPENDENCIES[module], f"{where}: {module} may not import {target}"
        assert ref.module == f"{MODULES_PKG}.{target}", (
            f"{where}: import {target} via its public package, not {ref.module}"
        )
        if target == "staff":
            assert set(ref.names) <= STAFF_PUBLIC_READ_API, (
                f"{where}: staff is read-only; only {sorted(STAFF_PUBLIC_READ_API)} may be used"
            )


def test_module_dependency_graph_is_acyclic() -> None:
    graph = {
        m: {ref.module.split(".")[2] for ref in cross_module_imports(m)} for m in module_names()
    }
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        assert node not in visiting, f"circular import: {' -> '.join((*path, node))}"
        if node in done:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep, (*path, node))
        visiting.discard(node)
        done.add(node)

    for module in graph:
        visit(module, ())


def test_core_does_not_import_modules() -> None:
    for path in (SRC / "core").rglob("*.py"):
        for ref in imports_in(path):
            assert not ref.module.startswith(MODULES_PKG), f"{path.name} imports {ref.module}"


@pytest.mark.parametrize("module", sorted(ALLOWED_DEPENDENCIES))
def test_services_and_routes_raise_only_app_errors(module: str) -> None:
    for layer in ("service.py", "routes.py"):
        path = MODULES_DIR / module / layer
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if isinstance(exc, ast.Name):
                assert exc.id not in BUILTIN_EXCEPTIONS, (
                    f"{module}/{layer}:{node.lineno} raises built-in {exc.id}; use an AppError"
                )
