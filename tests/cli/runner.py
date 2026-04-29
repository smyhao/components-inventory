"""
测试基础设施：测试上下文、CLI 执行器、测试套件和断言工具。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CLI_SCRIPT = PROJECT_ROOT / "inventory_cli.py"

# 供测试用的临时 config 目录
TEST_CONFIG_DIR = Path(tempfile.gettempdir()) / "components-inventory-test-config"


def color(text: str, name: str) -> str:
    codes = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "cyan": "\033[96m",
        "gray": "\033[90m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    return f"{codes.get(name, '')}{text}{codes['reset']}"


@dataclass
class TestContext:
    server: str = "http://localhost:5000"
    token: str = ""
    verbose: bool = False
    # 共享测试数据（跨测试函数传递 ID 等）
    shared: dict[str, Any] = field(default_factory=dict)

    def cli(self, *args: str, expect_ok: bool = True, input_text: str | None = None) -> CLIResult:
        return run_cli(
            *args,
            server=self.server,
            token=self.token,
            expect_ok=expect_ok,
            input_text=input_text,
        )


@dataclass
class CLIResult:
    exit_code: int
    stdout: str
    stderr: str
    json_data: dict[str, Any] | None = None
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def combined(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()

    def json_data_field(self, key: str, default: Any = None) -> Any:
        if self.json_data and isinstance(self.json_data.get("data"), dict):
            return self.json_data["data"].get(key, default)
        return default


@dataclass
class TestResult:
    name: str
    ok: bool = False
    skipped: bool = False
    message: str = ""
    elapsed: float = 0.0


class TestSuite:
    def __init__(self, ctx: TestContext, tests: list[tuple[str, Callable]]) -> None:
        self.ctx = ctx
        self.tests = tests

    def run(self) -> list[TestResult]:
        results = []
        self._setup()
        try:
            for name, func in self.tests:
                result = self._run_one(name, func)
                results.append(result)
                status = (
                    color("SKIP", "yellow") if result.skipped
                    else color("PASS", "green") if result.ok
                    else color("FAIL", "red")
                )
                msg = f"  {status}  {name}"
                if result.message and not result.ok and not result.skipped:
                    msg += color(f"  ({result.message})", "gray")
                elif result.skipped and result.message:
                    msg += color(f"  ({result.message})", "gray")
                print(msg)
        finally:
            self._teardown()
        return results

    def _run_one(self, name: str, func: Callable) -> TestResult:
        start = time.time()
        try:
            func(self.ctx)
            return TestResult(name=name, ok=True, elapsed=time.time() - start)
        except SkipTest as exc:
            return TestResult(name=name, skipped=True, message=str(exc), elapsed=time.time() - start)
        except AssertionError as exc:
            return TestResult(name=name, ok=False, message=str(exc), elapsed=time.time() - start)
        except Exception as exc:
            return TestResult(name=name, ok=False, message=f"{type(exc).__name__}: {exc}", elapsed=time.time() - start)

    def _setup(self) -> None:
        # 使用独立的测试 config 目录，避免污染用户真实配置
        os.environ["HOME"] = str(TEST_CONFIG_DIR)
        if TEST_CONFIG_DIR.exists():
            shutil.rmtree(TEST_CONFIG_DIR, ignore_errors=True)
        TEST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _teardown(self) -> None:
        # 清理测试 config
        if TEST_CONFIG_DIR.exists():
            shutil.rmtree(TEST_CONFIG_DIR, ignore_errors=True)


def run_cli(
    *args: str,
    server: str = "",
    token: str = "",
    expect_ok: bool = True,
    input_text: str | None = None,
) -> CLIResult:
    cmd = [sys.executable, str(CLI_SCRIPT)]
    if server:
        cmd += ["--server", server]
    if token:
        cmd += ["--token", token]
    cmd += list(args)

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            input=input_text,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        return CLIResult(exit_code=-1, stdout="", stderr="timeout", elapsed=time.time() - start)

    elapsed = time.time() - start
    result = CLIResult(
        exit_code=proc.returncode,
        stdout=proc.stdout.strip(),
        stderr=proc.stderr.strip(),
        elapsed=elapsed,
    )

    # 尝试解析 JSON 输出
    for output in (result.stdout, result.stderr):
        if output.startswith("{"):
            try:
                result.json_data = json.loads(output)
                break
            except json.JSONDecodeError:
                pass

    if expect_ok and not result.ok:
        raise AssertionError(
            f"CLI failed (exit={result.exit_code}): {result.combined[:500]}"
        )

    return result


class SkipTest(Exception):
    pass


def skip(msg: str = "") -> None:
    raise SkipTest(msg or "skipped")


# --- 断言工具 ---

def assert_eq(actual: Any, expected: Any, label: str = "") -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}" + (f" ({label})" if label else ""))


def assert_in(haystack: str, needle: str, label: str = "") -> None:
    if needle not in haystack:
        raise AssertionError(f"Expected '{needle}' in output" + (f" ({label})" if label else ""))


def assert_not_in(haystack: str, needle: str, label: str = "") -> None:
    if needle in haystack:
        raise AssertionError(f"Did not expect '{needle}' in output" + (f" ({label})" if label else ""))


def assert_json_code(result: CLIResult, expected_code: int = 0, label: str = "") -> None:
    assert result.json_data is not None, f"No JSON output" + (f" ({label})" if label else "")
    actual = result.json_data.get("code")
    assert_eq(actual, expected_code, label or "json code")


def assert_json_has(result: CLIResult, *keys: str, label: str = "") -> None:
    assert result.json_data is not None, "No JSON output"
    data = result.json_data.get("data")
    assert isinstance(data, dict), f"data is not a dict: {type(data)}"
    for key in keys:
        assert key in data, f"Missing key '{key}' in data" + (f" ({label})" if label else "")


def assert_exit_code(result: CLIResult, expected: int, label: str = "") -> None:
    assert_eq(result.exit_code, expected, label or "exit code")
