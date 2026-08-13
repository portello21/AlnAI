from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    print("=== ROG AI V8 VALIDATION ===")

    active = [
        ROOT / "app.py",
        ROOT / "core",
        ROOT / "agents",
        ROOT / "providers",
        ROOT / "tools",
    ]

    for path in active:
        if path.is_file():
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
        elif path.is_dir():
            ok = compileall.compile_dir(
                str(path),
                quiet=1,
                rx=r".*backup.*|.*__pycache__.*",
            )
            if not ok:
                raise SystemExit(f"Compile failure: {path}")

    print("ACTIVE_SOURCE_COMPILE_OK")
    run([sys.executable, "-m", "pytest", "-q", "tests/test_profile_access_v8.py", "tests/test_security_contract_v8.py", "tests/test_ui_contract_v8.py"])
    print("V8_CONTRACT_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
