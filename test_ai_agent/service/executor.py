"""
service/executor.py —— 第 5 步：执行测试脚本，收集结果

输入：pytest 脚本路径 + 对应的用例清单 cases
输出：list[TestResult]（每个用例一个结果）

对应测试工程师的动作：真正去"跑测试"，把 pass/fail 和报错信息记录下来。

注意：core 不直接碰 subprocess/系统，所以这层放在 service（外部依赖适配层）。
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

from core.models import TestCase, TestResult


def _extract_traceback(output: str, test_name: str) -> str:
    """从 pytest 输出里，粗略截取某个失败用例的报错段落。"""
    marker = "_" * 4 + test_name
    start = output.find(marker)
    if start == -1:
        return output[-2000:]          # 找不到就贴最后一段
    nxt = output.find("_" * 4, start + len(test_name) + 4)
    if nxt == -1:
        return output[start:]
    return output[start:nxt]


def run_tests(script_path: str, cases: list[TestCase], workdir: str = None) -> list[TestResult]:
    """
    运行 pytest 脚本，把结果按顺序映射回每个 TestCase。

    生成脚本里用例名是 test_00、test_01...，下标正好对应 cases 的顺序，
    所以能用下标把「运行结果」和「用例」一一对上。
    """
    # 1. 跑 pytest（-v 让每个用例输出 PASSED/FAILED 标记；注意别加 -q，会把标记行压掉）
    cmd = [sys.executable, "-m", "pytest", script_path, "-v", "--tb=short", "--no-header"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")

    # 2. 解析每个 test_XX 的 PASSED / FAILED / ERROR
    status_by_index: dict[int, str] = {}
    pattern = re.compile(r"::test_(\d+)\s+(PASSED|FAILED|ERROR|SKIPPED)")
    for m in pattern.finditer(output):
        status_by_index[int(m.group(1))] = m.group(2)

    # 3. 组装 TestResult
    results: list[TestResult] = []
    for i, case in enumerate(cases):
        status = status_by_index.get(i, "NOT_RUN")   # 没出现在输出里 = 压根没跑到
        passed = status in ("PASSED", "SKIPPED")     # SKIPPED 视为通过（没报错）
        results.append(TestResult(
            case=case,
            passed=passed,
            output=output,
            traceback=_extract_traceback(output, f"test_{i:02d}") if not passed else "",
        ))
    return results


def stop_test_server(port: int = 5000) -> bool:
    """
    停掉占用指定端口的进程（我们起的被测后端）。
    用 lsof 找到 PID 再 kill；找不到就返回 False。
    """
    lsof = shutil.which("lsof")
    if not lsof:
        return False
    proc = subprocess.run([lsof, "-ti", f":{port}"], capture_output=True, text=True)
    pids = [p for p in proc.stdout.split() if p]
    if not pids:
        return False
    subprocess.run(["kill", *pids], capture_output=True, text=True)
    return True


def cleanup(port: int = 5000, db_path: str = None, generated_dir: str = None) -> dict:
    """
    测试结束后的自动清理，返回各项是否清理成功。

    顺序很关键：先停服务，再删测试库。
    如果先删库而服务还在跑，下一个请求会因为找不到 users 表而报 500。
    """
    result = {"server_stopped": False, "db_removed": False, "generated_removed": False}

    # 1. 停掉被测后端（先停，再删库）
    result["server_stopped"] = stop_test_server(port)

    # 2. 删测试数据库，重置状态
    if db_path:
        db = Path(db_path)
        if db.exists():
            db.unlink()
            result["db_removed"] = True

    # 3. 删生成的测试脚本目录
    if generated_dir:
        d = Path(generated_dir)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            result["generated_removed"] = True

    return result
