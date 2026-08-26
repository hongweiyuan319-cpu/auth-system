"""
main.py —— AI 测试工程师 Agent 入口

用法：
    .venv/bin/python main.py --target ../qa_ai_agent/backend --prd docs/PRD.md

流程（全自动）：
    起后端 → 解析需求 → 扫描代码 → 生成用例 → 跑测试 → 失败归因 → 生成报告 → 清理
"""
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from core.requirements import parse_prd_llm
from core.scanner import scan
from core.test_generator import generate_llm
from service.executor import run_tests, cleanup, stop_test_server
from core.debugger import debug_llm
from core.reporter import write_report


def _port_open(port: int) -> bool:
    """探测端口是否已被监听。"""
    with socket.socket() as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def start_backend(target_dir: str, port: int = 5000):
    """
    启动被测后端并等端口就绪。
    用 start_new_session 让后端自成一个进程组，方便一键清掉（含 Flask 的 debug reloader 子进程）。
    """
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=target_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(40):            # 最多等 20 秒
        if _port_open(port):
            return proc
        time.sleep(0.5)
    return proc                    # 超时也返回，让测试自己暴露问题


def stop_backend(proc):
    """杀掉整个后端进程组（父进程 + debug reloader 子进程）。"""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def main():
    parser = argparse.ArgumentParser(description="AI 测试工程师 Agent")
    parser.add_argument("--target", required=True, help="被测代码目录（含 app.py）")
    parser.add_argument("--prd", required=True, help="需求文档路径（txt/md）")
    parser.add_argument("--out", default="report.md", help="报告输出路径")
    parser.add_argument("--port", type=int, default=5000, help="被测服务端口")
    args = parser.parse_args()

    target = str(Path(args.target).resolve())
    prd_path = str(Path(args.prd).resolve())
    db_path = str(Path(target) / "database.db")
    generated_dir = str(Path(__file__).resolve().parent / "generated")

    # 0. 先释放端口 + 清掉旧测试库（服务没起，删库安全）
    print("[0] 清理旧环境 ...")
    stop_test_server(args.port)
    Path(db_path).unlink(missing_ok=True)

    # 1. 启动被测后端
    print(f"[1/7] 启动被测后端 ({target}) ...")
    proc = start_backend(target, args.port)

    try:
        # 2. 解析需求 → 规则（LLM 优先，失败自动回退硬编码）
        print("[2/7] 解析需求规则 ...")
        rules = parse_prd_llm(prd_path)

        # 3. 扫描代码
        print("[3/7] 扫描被测代码 ...")
        funcs, endpoints = scan(target)

        # 4. 生成测试用例（LLM 优先，失败自动回退模板）
        print("[4/7] 生成测试用例 ...")
        cases, script = generate_llm(rules, endpoints, generated_dir)

        # 5. 执行测试
        print("[5/7] 执行测试 ...")
        results = run_tests(script, cases)

        # 6. 失败归因（LLM 优先，失败自动回退规则）
        print("[6/7] 失败归因 ...")
        reports = debug_llm(results, functions=funcs)

        # 7. 生成报告
        print("[7/7] 生成报告 ...")
        out = write_report(reports, args.out, results=results, target=target, prd_path=prd_path)
        print(f"报告已生成: {out}")

        n = len(reports)
        print(f"共发现 {n} 个 bug。" if n else "未发现 bug。")
        return 1 if n else 0
    finally:
        # 收尾：停后端（整组杀掉）+ 删测试库（生成脚本保留可复现）
        stop_backend(proc)
        info = cleanup(port=args.port, db_path=db_path)
        print(f"清理: {info}")


if __name__ == "__main__":
    sys.exit(main())
