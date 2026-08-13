from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def active_python_files() -> list[Path]:
    roots = [ROOT / "app.py", ROOT / "core", ROOT / "agents", ROOT / "providers", ROOT / "tools", ROOT / "tests"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(
                p for p in root.rglob("*.py")
                if "backup" not in p.name.lower() and "__pycache__" not in p.parts
            )
    return sorted(set(files))


def main() -> int:
    print("=== ROG AI V8/V9 VALIDATION ===")
    files = active_python_files()
    for path in files:
        py_compile.compile(str(path), doraise=True)
    print(f"ACTIVE_SOURCE_COMPILE_OK ({len(files)} files)")

    contract_tests = [
        "tests/test_auth_v8.py",
        "tests/test_profile_access_v8.py",
        "tests/test_security_contract_v8.py",
        "tests/test_security_v8.py",
        "tests/test_ui_contract_v8.py",
        "tests/test_source_contract_v8.py",
        "tests/test_apptest_ui_v8.py",
        "tests/test_provider_policy_v9.py",
        "tests/test_rag_isolation_v9.py",
    ]
    run([sys.executable, "-m", "pytest", "-q", *contract_tests])
    print("V8_V9_CONTRACT_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
