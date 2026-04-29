"""
Components Inventory CLI 集成测试入口

用法:
  python text/cli/test_cli.py                                    # 运行全部测试
  python text/cli/test_cli.py --group config                     # 只运行 config 测试
  python text/cli/test_cli.py --group connection                 # 只运行 ping/stats 测试
  python text/cli/test_cli.py --group components                 # 只运行 components 测试
  python text/cli/test_cli.py --group boxes                      # 只运行 boxes 测试
  python text/cli/test_cli.py --group stock                      # 只运行 stock 测试
  python text/cli/test_cli.py --group options                    # 只运行全局选项测试
  python text/cli/test_cli.py --group errors                     # 只运行错误处理测试

  python text/cli/test_cli.py --server http://192.168.1.20:5000
  python text/cli/test_cli.py --server http://192.168.1.20:5000 --token change-me

前置条件:
  1. Flask 服务已启动（python app.py）
  2. 如果服务启用了 Token 鉴权，需要通过 --token 传入
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from text.cli.runner import TestContext, TestResult, TestSuite, color

TEST_GROUPS: dict[str, list[str]] = {
    "config": [
        "text.cli.test_config",
    ],
    "connection": [
        "text.cli.test_connection",
    ],
    "components": [
        "text.cli.test_components",
    ],
    "boxes": [
        "text.cli.test_boxes",
    ],
    "stock": [
        "text.cli.test_stock",
    ],
    "options": [
        "text.cli.test_options",
    ],
    "errors": [
        "text.cli.test_errors",
    ],
}

ALL_GROUPS = list(TEST_GROUPS.keys())


def import_test_modules(groups: list[str]) -> list:
    modules = []
    seen: set[str] = set()
    for group in groups:
        for module_name in TEST_GROUPS.get(group, []):
            if module_name in seen:
                continue
            seen.add(module_name)
            import importlib
            module = importlib.import_module(module_name)
            modules.append(module)
    return modules


def collect_tests(modules: list) -> list:
    tests = []
    for module in modules:
        for attr_name in sorted(dir(module)):
            if attr_name.startswith("test_"):
                func = getattr(module, attr_name)
                if callable(func):
                    tests.append((f"{module.__name__}.{attr_name}", func))
    return tests


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI integration test runner")
    parser.add_argument("--server", default="http://localhost:5000", help="Server URL")
    parser.add_argument("--token", default="", help="API token")
    parser.add_argument("--group", action="append", dest="groups", choices=ALL_GROUPS, help="Test group(s) to run")
    parser.add_argument("--list", action="store_true", help="List test names without running")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    groups = args.groups or ALL_GROUPS
    ctx = TestContext(
        server=args.server,
        token=args.token,
        verbose=args.verbose,
    )

    modules = import_test_modules(groups)
    tests = collect_tests(modules)

    if args.list:
        for name, _func in tests:
            print(name)
        return 0

    suite = TestSuite(ctx, tests)
    results = suite.run()

    # summary
    passed = sum(1 for r in results if r.ok)
    failed = sum(1 for r in results if not r.ok)
    skipped = sum(1 for r in results if r.skipped)
    total = len(results)
    elapsed = sum(r.elapsed for r in results)

    print()
    print("=" * 60)
    if failed == 0:
        print(color(f"  ALL PASSED  {passed}/{total}  ({elapsed:.1f}s)", "green"))
    else:
        print(color(f"  FAILED {failed}, PASSED {passed}, TOTAL {total}  ({elapsed:.1f}s)", "red"))
    if skipped:
        print(color(f"  SKIPPED {skipped}", "yellow"))

    if failed > 0:
        print()
        print("  Failed tests:")
        for r in results:
            if not r.ok and not r.skipped:
                print(f"    - {r.name}: {r.message}")

    print("=" * 60)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
