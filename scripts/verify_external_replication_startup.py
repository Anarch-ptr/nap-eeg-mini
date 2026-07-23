"""Isolated, non-scientific Phase II-A startup verifier."""

from __future__ import annotations

import json
import os
import sys
import sysconfig
from dataclasses import asdict
from pathlib import Path


def _abort(reason: str) -> None:
    raise SystemExit(f"ISOLATED_STARTUP_REFUSED: {reason}")


def _canonical(path: str | Path, *, strict: bool = False) -> Path:
    return Path(path).resolve(strict=strict)


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _inside(path: Path, root: Path) -> bool:
    path_text = os.path.normcase(str(path))
    root_text = os.path.normcase(str(root))
    return path_text == root_text or path_text.startswith(root_text + os.sep)


def _approved_initial_stdlib_roots() -> tuple[Path, ...]:
    base = _canonical(sys.base_prefix)
    roots = {
        _canonical(base),
        _canonical(base / "DLLs"),
        _canonical(base / "Lib"),
        _canonical(base / f"python{sys.version_info.major}{sys.version_info.minor}.zip"),
    }
    for key in ("stdlib", "platstdlib"):
        value = sysconfig.get_path(key)
        if value:
            roots.add(_canonical(value))
    return tuple(sorted(roots, key=lambda item: str(item).lower()))


def _reject_untrusted_initial_sys_path(
    root: Path,
    venv: Path,
    site_packages: Path,
) -> tuple[Path, ...]:
    stdlib_roots = _approved_initial_stdlib_roots()
    rejected: list[str] = []
    for entry in sys.path:
        if entry == "":
            rejected.append("<empty-cwd>")
            continue
        path = _canonical(entry)
        if any(part.lower() == "site-packages" for part in path.parts):
            rejected.append(entry)
            continue
        if _inside(path, site_packages) or _inside(path, venv):
            rejected.append(entry)
            continue
        if _inside(path, root):
            rejected.append(entry)
            continue
        if any(_inside(path, allowed) or _same_path(path, allowed) for allowed in stdlib_roots):
            continue
        rejected.append(entry)
    if rejected:
        _abort("UNTRUSTED_INITIAL_SYS_PATH:" + "|".join(rejected))
    return stdlib_roots


def _verify_module_origin(name: str, approved_roots: tuple[Path, ...]) -> None:
    module = sys.modules.get(name)
    if module is None:
        return
    locations: list[Path] = []
    module_file = getattr(module, "__file__", None)
    if module_file:
        locations.append(_canonical(module_file))
    spec = getattr(module, "__spec__", None)
    search_locations = getattr(spec, "submodule_search_locations", None)
    if search_locations:
        locations.extend(_canonical(location) for location in search_locations)
    if not locations:
        return
    if not all(
        any(_inside(location, allowed) for allowed in approved_roots)
        for location in locations
    ):
        _abort(f"UNAPPROVED_IMPORT_ORIGIN:{name}")


def _verify_loaded_origins(root: Path, site_packages: Path) -> None:
    for name in sorted(sys.modules):
        if name == "src" or name.startswith("src.external_replication"):
            _verify_module_origin(name, (root,))
        elif name.split(".", 1)[0] in {
            "mne",
            "moabb",
            "numpy",
            "pandas",
            "scipy",
            "sklearn",
            "torch",
        }:
            _verify_module_origin(name, (site_packages,))


def _prepare_trusted_import_path() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    venv = (root / ".venv").resolve()
    expected_python = (venv / "Scripts" / "python.exe").resolve()
    if os.path.normcase(str(Path(sys.executable).resolve())) != os.path.normcase(
        str(expected_python)
    ):
        _abort("NONCANONICAL_INTERPRETER")
    required_flags = {
        "isolated": sys.flags.isolated,
        "ignore_environment": sys.flags.ignore_environment,
        "no_user_site": sys.flags.no_user_site,
        "no_site": sys.flags.no_site,
        "safe_path": sys.flags.safe_path,
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
    }
    if required_flags != {
        "isolated": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "no_site": 1,
        "safe_path": True,
        "dont_write_bytecode": 1,
    }:
        _abort("REQUIRES_-I_-E_-B_-S")

    site_packages = (venv / "Lib" / "site-packages").resolve()
    if not site_packages.is_dir():
        _abort("CANONICAL_SITE_PACKAGES_MISSING")
    stdlib_roots = _reject_untrusted_initial_sys_path(root, venv, site_packages)
    sys.prefix = str(venv)
    # Stdlib first prevents repository-root shadowing of Python itself; the
    # canonical venv precedes the repository root to prevent dependency shadowing.
    sys.path[:] = [str(path) for path in stdlib_roots] + [
        str(site_packages),
        str(root),
    ]
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE"):
        os.environ.pop(name, None)
    return root, site_packages


def main() -> int:
    root, site_packages = _prepare_trusted_import_path()
    from src.external_replication.startup import (
        enforce_pre_scientific_startup_or_abort,
    )

    result = enforce_pre_scientific_startup_or_abort(root)
    _verify_loaded_origins(root, site_packages)
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
