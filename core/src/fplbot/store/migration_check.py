"""CI check: migrations are expand-only unless labelled as a contract step (ADR 0003).

A rollback runs the previous image against the new schema, so an ``upgrade()`` must not drop or
rename anything the previous image still reads. Once no deployed image uses the old shape, a
separate migration removes it and says so with a module-level label::

    contract_step = True

Usage: ``python -m fplbot.store.migration_check [VERSIONS_DIR]`` (defaults to this package's
``migrations/versions``). Exits 1 and lists each offending operation if any are found.
"""

import ast
import re
import sys
from collections.abc import Sequence
from pathlib import Path

DEFAULT_VERSIONS_DIR = Path(__file__).parent / "migrations" / "versions"

CONTRACT_LABEL = "contract_step"
_DESTRUCTIVE_OPS = {"drop_table", "drop_column", "rename_table"}
_DESTRUCTIVE_SQL = re.compile(r"\b(DROP\s+(TABLE|COLUMN)|RENAME)\b", re.IGNORECASE)


def _is_labelled_contract_step(module: ast.Module) -> bool:
    for node in module.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        named = any(isinstance(t, ast.Name) and t.id == CONTRACT_LABEL for t in targets)
        if named and isinstance(value, ast.Constant) and value.value is True:
            return True
    return False


def _upgrade_function(module: ast.Module) -> ast.FunctionDef | None:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            return node
    return None


def _destructive_sql(call: ast.Call) -> bool:
    """Whether any string literal inside ``op.execute(...)`` drops or renames something."""
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _DESTRUCTIVE_SQL.search(node.value)
        for node in ast.walk(call)
    )


def _destructive_operations(upgrade: ast.FunctionDef) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(upgrade):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name in _DESTRUCTIVE_OPS:
            found.append((node.lineno, name))
        elif name == "alter_column" and any(k.arg == "new_column_name" for k in node.keywords):
            found.append((node.lineno, "alter_column(new_column_name=...)"))
        elif name == "execute" and _destructive_sql(node):
            found.append((node.lineno, "execute() with DROP/RENAME SQL"))
    return found


def problems_in(path: Path) -> list[str]:
    """Each destructive operation in ``path``'s ``upgrade()``, as ``file:line: message``."""
    module = ast.parse(path.read_text(), filename=str(path))
    if _is_labelled_contract_step(module):
        return []
    upgrade = _upgrade_function(module)
    if upgrade is None:
        return []
    return [
        f"{path.name}:{line}: {operation} in upgrade() is not backward-compatible; "
        f"expand first, then contract in a migration labelled `{CONTRACT_LABEL} = True`"
        for line, operation in _destructive_operations(upgrade)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    directory = Path(args[0]) if args else DEFAULT_VERSIONS_DIR
    problems = [p for path in sorted(directory.glob("*.py")) for p in problems_in(path)]
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
