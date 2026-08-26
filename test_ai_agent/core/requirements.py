"""
core/requirements.py —— 读需求文档(PRD) → 拆成规则表

输入：PRD 文件路径（txt / md）
输出：list[RequirementRule]   （一张张"规则表"）

对应测试工程师的动作：把需求文档"拆规则"。

解析策略（LLM 优先 + 硬编码兜底）：
- parse_prd_llm()：优先用 LLM 解析任意写法的 PRD，产出符合 RequirementRule schema 的 JSON。
- parse_prd()：确定性兜底，用"正则/关键词"解析常见的规则写法（长度/必填/格式）。
  没配 LLM_API_KEY 或 LLM 解析失败时，流水线自动回退到 parse_prd()，保证不会断。
"""
import re
from pathlib import Path

from core.models import RequirementRule
from service.llm import chat_json


def _strip_marker(line: str) -> str:
    """去掉行首的列表符号，如 '1. '、'- '、'* '、'• '"""
    return re.sub(r"^[\s]*(?:\d+[.、)]|[-*•])\s*", "", line).strip()


def _parse_line(raw_line: str):
    """把 PRD 里的一行文字，解析成一张 RequirementRule 表；解析不了返回 None。"""
    line = _strip_marker(raw_line)

    # 1) 长度类规则：如「用户名长度不能少于 6 位」
    #    ^(.+?)长度     开头抓出"作用字段"（如"用户名"）
    #    .*?(\d+)\s*位  抓出数字 6
    m = re.search(r"^(.+?)长度.*?(\d+)\s*位", line)
    if m:
        field = m.group(1).strip()
        return RequirementRule(
            field=field,
            description=line,          # 用去掉列表符号的行，避免报告里带 '2. '
            min_len=int(m.group(2)),
        )

    # 2) 必填类规则：如「用户名不能为空」
    m = re.search(r"^(.+?)不能为空", line)
    if m:
        field = m.group(1).strip()
        return RequirementRule(
            field=field,
            description=line,
            required=True,
        )

    # 3) 格式类规则：如「用户名只能包含字母和数字」
    m = re.search(r"^(.+?)只能包含字母和数字", line)
    if m:
        field = m.group(1).strip()
        return RequirementRule(
            field=field,
            description=line,
            pattern=r"^[a-zA-Z0-9]+$",
        )

    return None  # 这行看不懂，跳过


def parse_prd(prd_path: str) -> list[RequirementRule]:
    """读 PRD 文件，把每行能识别的规则解析成 RequirementRule 列表。"""
    rules: list[RequirementRule] = []
    with open(prd_path, encoding="utf-8") as f:
        for raw_line in f:
            if not raw_line.strip():
                continue                      # 空行跳过
            if raw_line.lstrip().startswith("#"):
                continue                      # markdown 标题(#)跳过
            rule = _parse_line(raw_line)
            if rule:
                rules.append(rule)
    return rules


# ── LLM 解析部分（LLM 优先，硬编码兜底）──

_SCHEMA_PROMPT = """\
你是资深测试工程师，负责把需求文档解析成结构化规则。
只输出 JSON 数组，每个元素是一条规则，字段如下（严格遵循）：
  field       (必填, 字符串) 作用字段的中文名，如 "用户名"
  description (必填, 字符串) 规则的人类可读描述
  required    (可选, 布尔)   是否必填
  min_len     (可选, 整数)   最小长度
  max_len     (可选, 整数)   最大长度
  pattern     (可选, 字符串) 正则规则
只输出 JSON 数组，不要任何解释或多余文字。
"""


def _validate_rule(raw) -> RequirementRule | None:
    """校验 LLM 返回的 dict 是否符合 RequirementRule schema；不合规返回 None。"""
    if not isinstance(raw, dict):
        return None
    field = raw.get("field")
    if not isinstance(field, str) or not field.strip():
        return None          # field 是必填，缺了就丢
    rule = RequirementRule(
        field=field.strip(),
        description=str(raw.get("description") or "").strip(),
        required=bool(raw.get("required", False)),
    )
    if isinstance(raw.get("min_len"), int):
        rule.min_len = raw["min_len"]
    if isinstance(raw.get("max_len"), int):
        rule.max_len = raw["max_len"]
    if isinstance(raw.get("pattern"), str):
        rule.pattern = raw["pattern"]
    return rule


def parse_prd_llm(prd_path: str, fallback: bool = True) -> list[RequirementRule]:
    """
    用 LLM 解析 PRD → 规则列表。
    - 成功：返回 LLM 解析且通过 schema 校验的规则。
    - 失败（没配 key / 网络错 / JSON 解析不了 / 全是无效项）：
      fallback=True 时回退到硬编码 parse_prd()，保证流水线不断。
    """
    text = Path(prd_path).read_text(encoding="utf-8")
    user_prompt = f"{_SCHEMA_PROMPT}\n需求文档如下：\n{text}"

    try:
        data = chat_json(user_prompt, system="你只输出 JSON。")
        items = data if isinstance(data, list) else [data]
        rules = [r for r in (_validate_rule(it) for it in items) if r is not None]
        if rules:
            return rules
    except Exception as exc:                     # 没 key / 网络 / 解析失败…
        print(f"[requirements] LLM 解析失败，改用硬编码兜底：{type(exc).__name__}")

    if fallback:
        return parse_prd(prd_path)
    raise RuntimeError("LLM 解析 PRD 失败，且已关闭兜底")
