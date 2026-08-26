"""
core/debugger.py —— 失败归因（判定 FAIL 是真 bug 还是用例/环境问题）

输入：list[TestResult]（executor 跑完的结果）+ 可选 functions（scanner 函数清单）
输出：list[BugReport]（确认的真 bug）

对应测试工程师的动作：测试挂了之后要"排查"——
  - 是环境/用例问题（服务没起、脚本写错）→ 不算 bug，修正后重跑
  - 是代码行为不符合规则 → 写成 bug 单

归因策略（LLM 优先 + 规则兜底）：
- debug_llm()：优先让 LLM 判断真假 bug、定严重度、写修复建议（出 BugReport JSON）。
- debug()：确定性兜底，用规则/关键词归因。
  没配 LLM_API_KEY 或 LLM 失败时自动回退，保证流水线不断。
"""
import json
import re

from core.models import TestResult, BugReport, Severity, RequirementRule
from core.test_generator import _to_code_field
from service.llm import chat_json


def _is_env_or_script_problem(result: TestResult) -> bool:
    """粗略判断：这个失败是不是环境/脚本问题（而不是代码 bug）。"""
    if result.passed:
        return False
    tb = result.traceback
    if not tb:
        return True                       # 连报错都没有 → 异常情况，先不当 bug
    markers = ["ConnectionError", "ModuleNotFoundError", "SyntaxError",
               "NameError", "ImportError"]
    return any(m in tb for m in markers)


def _extract_actual_status(traceback: str) -> str:
    """从断言信息里提取实际状态码：'实际 200' → '200'。"""
    m = re.search(r"实际 (\d+)", traceback)
    return m.group(1) if m else "?"


def _locate(code_field: str, functions) -> dict:
    """在函数清单里找"校验相关函数"，返回 {file, line}。

    策略：优先找名字像校验函数（含 valid/check/verify）且参数含该字段的；
          没有就退而求其次，找任意含该字段参数的函数。
    """
    def _has_field(f) -> bool:
        return code_field in f.params

    def _looks_like_validation(f) -> bool:
        name = f.name.lower()
        return any(k in name for k in ("valid", "check", "verify"))

    for f in functions or []:
        if _has_field(f) and _looks_like_validation(f):
            return {"file": f.file, "line": f.line}
    for f in functions or []:
        if _has_field(f):
            return {"file": f.file, "line": f.line}
    return {"file": "未知", "line": None}


def _suggestion(rule: RequirementRule) -> str:
    """按规则类型给出修复建议。"""
    if rule.min_len:
        return f"在注册接口增加校验：{rule.field} 长度不能少于 {rule.min_len} 位"
    if rule.pattern:
        return f"在注册接口增加校验：{rule.field} 需匹配格式 {rule.pattern}"
    if rule.required:
        return f"在注册接口增加校验：{rule.field} 不能为空"
    return "补充对应校验逻辑"


def _build_report(result: TestResult, functions) -> BugReport:
    """把一个失败结果变成一张 BugReport。"""
    case = result.case
    actual = _extract_actual_status(result.traceback)
    loc = _locate(_to_code_field(case.rule.field), functions)

    return BugReport(
        title=f"未执行校验：{case.rule.description}",
        file=loc["file"],
        line=loc["line"],
        severity=Severity.MAJOR,
        rule=case.rule,
        reproduction_steps=[
            "1. 调用被测注册接口",
            f"2. 提交数据：{case.input_data}",
            f"3. 期望返回 {case.expected_status}（拒绝），实际返回 {actual}（未拒绝）",
        ],
        expected=f"返回状态码 {case.expected_status}（拒绝该输入）",
        actual=f"返回状态码 {actual}（未拒绝，违反规则）",
        suggestion=_suggestion(case.rule),
        evidence=result.traceback[:500],
    )


def debug(results: list[TestResult], functions=None) -> list[BugReport]:
    """
    对每个失败结果做归因：
      - 环境/脚本问题 → 跳过（不算 bug）
      - 断言失败     → 生成 BugReport
    """
    reports: list[BugReport] = []
    for r in results:
        if r.passed:
            continue                       # 通过的跳过
        if _is_env_or_script_problem(r):
            continue                       # 环境/脚本问题跳过
        reports.append(_build_report(r, functions))
    return reports


# ── LLM 归因部分（LLM 优先，规则兜底）──


def _validate_report(raw, failed_results) -> BugReport | None:
    """校验 LLM 返回的 bug 单 dict；不合规返回 None。"""
    if not isinstance(raw, dict) or raw.get("is_bug") is False:
        return None                        # 不是 dict / LLM 判定非 bug → 丢
    idx = raw.get("index")
    src = failed_results[idx] if (isinstance(idx, int) and 0 <= idx < len(failed_results)) else None
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    sev = Severity._value2member_map_.get(str(raw.get("severity", "")), Severity.MAJOR)
    return BugReport(
        title=title.strip(),
        file=str(raw.get("file") or "未知"),
        line=raw.get("line"),
        severity=sev,
        rule=src.case.rule if src else None,
        expected=str(raw.get("expected") or ""),
        actual=str(raw.get("actual") or ""),
        suggestion=str(raw.get("suggestion") or ""),
        reproduction_steps=[str(s) for s in (raw.get("reproduction_steps") or [])],
        evidence=src.traceback[:500] if src else "",
    )


def debug_llm(results: list[TestResult], functions=None, fallback: bool = True) -> list[BugReport]:
    """
    用 LLM 对每个失败做归因。
    - 成功：返回 LLM 判定且通过校验的 bug 单（缺位置的会用规则定位补齐）。
    - 失败：fallback=True 时回退到规则版 debug()。
    """
    failed = [r for r in results if not r.passed]
    if not failed:
        return []

    failures_json = json.dumps([
        {
            "index": i,
            "case_name": r.case.name,
            "rule": r.case.rule.description,
            "rule_type": {
                "min_len": r.case.rule.min_len,
                "required": r.case.rule.required,
                "pattern": r.case.rule.pattern,
            },
            "input_data": r.case.input_data,
            "expected_status": r.case.expected_status,
            "traceback": r.traceback[:800],
        }
        for i, r in enumerate(failed)
    ], ensure_ascii=False, indent=2)

    user_prompt = (
        "你是资深测试工程师，请对以下失败的测试用例做归因。\n\n"
        f"失败用例列表（JSON）：\n{failures_json}\n\n"
        "输出 JSON 数组，每个元素对应一个失败用例，格式：\n"
        '  {"index": 失败用例下标, "is_bug": true/false, "title": "标题", '
        '"severity": "阻塞/严重/主要/次要/轻微", "file": "文件路径", "line": 行号, '
        '"expected": "期望行为", "actual": "实际行为", "suggestion": "修复建议", '
        '"reproduction_steps": ["步骤1", "步骤2"]}\n'
        "规则：\n"
        "1. 若是服务没起、脚本语法错这类环境/脚本问题，is_bug 填 false。\n"
        "2. 若是断言不通过（实际返回码与期望不一致），说明代码没遵守规则，"
        "is_bug 填 true，并给修复建议。\n"
        "3. file/line 若无法判断，file 留空字符串、line 用 null。\n"
        "只输出 JSON 数组，不要多余文字。"
    )

    try:
        data = chat_json(user_prompt, system="你只输出 JSON。")
        items = data if isinstance(data, list) else [data]
        reports: list[BugReport] = []
        for raw in items:
            rep = _validate_report(raw, failed)
            if rep is None:
                continue
            # 位置兜底：LLM 没给就用规则定位补齐
            if not rep.file or rep.file == "未知":
                loc = _locate(_to_code_field(rep.rule.field) if rep.rule else "", functions)
                rep.file = loc["file"]
                rep.line = loc["line"]
            reports.append(rep)
        if reports:
            return reports
    except Exception as exc:
        print(f"[debugger] LLM 归因失败，改用规则兜底：{type(exc).__name__}")

    if fallback:
        return debug(results, functions)
    raise RuntimeError("LLM 归因失败，且已关闭兜底")