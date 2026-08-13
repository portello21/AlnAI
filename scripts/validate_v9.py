from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tests = [
        "tests/test_provider_policy_v9.py",
        "tests/test_llm_router_v9.py",
        "tests/test_rag_isolation_v9.py",
    ]
    subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, check=True)
    print("V9_CONTRACT_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
