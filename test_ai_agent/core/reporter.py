"""
core/reporter.py —— 第 7 步：把 BugReport 渲染成 Markdown 报告

输入：list[BugReport] + 测试汇总信息
输出：报告字符串，或直接写盘

对应测试工程师的动作：把确认的 bug 整理成一份能交付的测试报告。
"""
from pathlib import Path


def render_report(reports, results=None, target=None, prd_path=None) -> str:
    """渲染一份 Markdown 测试报告。"""
    lines = ["# 自动化测试报告", ""]

    # ── 概览 ──
    lines.append("## 概览")
    if target:
        lines.append(f"- 被测代码：`{target}`")
    if prd_path:
        lines.append(f"- 需求文档：`{prd_path}`")
    if results is not None:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        lines.append(f"- 用例：共 {total} 条，通过 {passed} 条，失败 {total - passed} 条")
    lines.append(f"- 确认 Bug：**{len(reports)}** 个")
    lines.append("")

    if not reports:
        lines.append("✅ 未发现违反需求的 bug。")
        return "\n".join(lines)

    # ── 每个 bug 一节 ──
    for i, b in enumerate(reports, 1):
        lines.append(f"## Bug {i}：{b.title}")
        lines.append("")
        lines.append(f"- **严重度**：{b.severity.value}")
        lines.append(f"- **位置**：`{b.file}:{b.line}`")
        if b.rule:
            lines.append(f"- **违反规则**：{b.rule.description}")
        lines.append(f"- **期望**：{b.expected}")
        lines.append(f"- **实际**：{b.actual}")
        lines.append(f"- **建议修复**：{b.suggestion}")
        lines.append("")
        lines.append("**复现步骤**：")
        for s in b.reproduction_steps:
            lines.append(s)
        lines.append("")
        if b.evidence:
            lines.append("**证据**：")
            lines.append("```")
            lines.append(b.evidence.strip())
            lines.append("```")
            lines.append("")
    return "\n".join(lines)


def write_report(reports, out_path="report.md", **kwargs) -> str:
    """渲染并写盘，返回报告路径。"""
    content = render_report(reports, **kwargs)
    Path(out_path).write_text(content, encoding="utf-8")
    return out_path
