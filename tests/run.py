"""Zero-dependency test runner (pytest-free): import each test module, call test_*."""

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODULES = ["test_signing", "test_receipts", "test_wallet"]


def main() -> int:
    total = fails = 0
    for modname in MODULES:
        try:
            mod = __import__(modname)
        except Exception:
            print("IMPORT FAIL", modname)
            traceback.print_exc()
            fails += 1
            continue
        for name in dir(mod):
            if not name.startswith("test_"):
                continue
            total += 1
            fn = getattr(mod, name)
            try:
                fn()
                print("PASS", f"{modname}.{name}")
            except Exception:
                fails += 1
                print("FAIL", f"{modname}.{name}")
                traceback.print_exc()
    print()
    print(f"{total - fails}/{total} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
