"""
core/test_generator.py —— 用「规则表 + 被测接口」生成 pytest 测试脚本

输入：
  rules     -> list[RequirementRule]   解析出来的规则
  endpoints -> list[EndpointInfo]      扫描出来的接口
  以及一个输出目录
输出：
  (cases, script_path)
  cases       -> list[TestCase]        生成的用例清单
  script_path -> str                   生成的 pytest 脚本文件路径

对应测试工程师的动作：设计用例（正常 + 边界 + 异常），写成可执行的测试脚本。

用例设计策略（LLM 优先 + 模板兜底）：
- generate_llm()：优先让 LLM 设计用例（出 TestCase JSON），
  由确定性代码校验 schema 并渲染成 pytest 脚本。
- generate()：确定性兜底，用模板按规则造用例。
  没配 LLM_API_KEY 或 LLM 失败时自动回退，保证流水线不断。
"""
import json
from pathlib import Path

from core.models import RequirementRule, EndpointInfo, TestCase
from service.llm import chat_json


# ── 中文字段 → 代码字段 映射（先写死，以后换 LLM）──
_FIELD_MAP = {
    "用户名": "username",
    "密码": "password",
}

# ── 每个字段的"合法值"：构造用例时，别的字段用合法值，只把被测字段改成违规值 ──
_FIELD_VALID_VALUES = {
    "username": "test_user_001",
    "password": "validpass123",
}

# 被测服务根地址（不含路径，路径由 endpoint.path 拼接）
BASE_URL = "http://127.0.0.1:5000"


def _to_code_field(field: str) -> str:
    """中文规则字段 → 代码字段名（认不出就原样返回）"""
    return _FIELD_MAP.get(field, field)


def _valid_payload(code_fields: list) -> dict:
    """用合法值填好所有字段，作为"干净底子"。"""
    return {f: _FIELD_VALID_VALUES.get(f, f"valid_{f}") for f in code_fields}


def _build_cases_for_rule(rule: RequirementRule, code_fields: list) -> list[TestCase]:
    """把一条规则变成一批 TestCase（重点造"违反规则"的负例）。"""
    code_field = _to_code_field(rule.field)
    cases: list[TestCase] = []

    if rule.required:
        payload = _valid_payload(code_fields)
        payload[code_field] = ""          # 违规：字段为空
        cases.append(TestCase(
            name=f"{rule.field}不能为空 应拒绝",
            rule=rule,
            input_data=payload,
            expected_status=400,
        ))

    if rule.min_len:
        payload = _valid_payload(code_fields)
        payload[code_field] = "a" * (rule.min_len - 1)   # 违规：长度刚好差一位
        cases.append(TestCase(
            name=f"{rule.field}长度小于{rule.min_len} 应拒绝",
            rule=rule,
            input_data=payload,
            expected_status=400,
        ))

    if rule.pattern:
        payload = _valid_payload(code_fields)
        payload[code_field] = "@@@@@"      # 违规：含非法字符
        cases.append(TestCase(
            name=f"{rule.field}含非法字符 应拒绝",
            rule=rule,
            input_data=payload,
            expected_status=400,
        ))

    return cases


def _render_script(endpoint: EndpointInfo, cases: list[TestCase]) -> str:
    """把用例清单渲染成一段 pytest 脚本源码。"""
    lines = [
        f'"""由 test_generator 自动生成 —— 测试接口 {endpoint.path}"""',
        "import requests",
        "",
        f'BASE_URL = "{BASE_URL}"',
        "",
    ]
    for i, c in enumerate(cases):
        data_repr = repr(c.input_data)
        lines.append(f"def test_{i:02d}():")
        lines.append(f'    """{c.name}"""')
        lines.append(f'    r = requests.post(f"{{BASE_URL}}{endpoint.path}", json={data_repr})')
        lines.append(
            f'    assert r.status_code == {c.expected_status}, '
            f'f"期望 {c.expected_status}，实际 {{r.status_code}}: {{r.text}}"'
        )
        lines.append("")
    return "\n".join(lines)


def generate(rules, endpoints, out_dir="generated", endpoint_path="/api/register"):
    """
    针对指定接口，把规则变成用例，生成 pytest 脚本。
    返回 (cases, script_path)。
    """
    # 1. 找到被测接口
    endpoint = next((e for e in endpoints if e.path == endpoint_path), None)
    if endpoint is None:
        raise ValueError(f"在扫描结果里找不到接口 {endpoint_path}")

    # 2. 收集接口相关的字段（这里先取规则里出现的所有字段）
    code_fields = sorted({_to_code_field(r.field) for r in rules})

    # 3. 规则 → 用例
    cases: list[TestCase] = []
    for rule in rules:
        cases.extend(_build_cases_for_rule(rule, code_fields))

    # 4. 用例 → 脚本
    script_source = _render_script(endpoint, cases)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = out_dir / f"test_{endpoint.function}.py"
    script_path.write_text(script_source, encoding="utf-8")

    return cases, str(script_path)


# ── LLM 生成用例部分（LLM 优先，模板兜底）──


def _validate_case(raw, rules) -> TestCase | None:
    """校验 LLM 返回的用例 dict；不合规返回 None。"""
    if not isinstance(raw, dict):
        return None
    idx = raw.get("rule_index")
    if not isinstance(idx, int) or not (0 <= idx < len(rules)):
        return None                      # 引用了不存在的规则 → 丢
    input_data = raw.get("input_data")
    if not isinstance(input_data, dict) or not input_data:
        return None
    status = raw.get("expected_status")
    if not isinstance(status, int):
        status = 400
    return TestCase(
        name=str(raw.get("name") or f"LLM用例-规则{idx}"),
        rule=rules[idx],
        input_data=input_data,
        expected_status=status,
    )


def generate_llm(rules, endpoints, out_dir="generated", endpoint_path="/api/register", fallback=True):
    """
    让 LLM 根据「规则 + 被测接口」设计用例，生成 pytest 脚本。
    - 成功：返回 LLM 设计且通过校验的用例（会去重）。
    - 失败：fallback=True 时回退到模板版 generate()。
    """
    endpoint = next((e for e in endpoints if e.path == endpoint_path), None)
    if endpoint is None:
        raise ValueError(f"在扫描结果里找不到接口 {endpoint_path}")

    rules_json = json.dumps([
        {"field": r.field, "description": r.description,
         "min_len": r.min_len, "max_len": r.max_len,
         "required": r.required, "pattern": r.pattern}
        for r in rules
    ], ensure_ascii=False, indent=2)

    user_prompt = (
        "你是测试工程师，请根据需求规则和被测接口设计测试用例。\n\n"
        f"需求规则列表（JSON）：\n{rules_json}\n\n"
        f"被测接口：\n- 路径: {endpoint.methods} {endpoint.path}\n"
        f"- 处理函数: {endpoint.function}\n\n"
        "要求：\n"
        "1. 每条规则至少设计一个【违反该规则】的负例。\n"
        "2. 输出 JSON 数组，每项格式：\n"
        '   {"name": "用例名", "rule_index": 对应规则下标, '
        '"input_data": {"英文参数字段": 值}, "expected_status": 期望状态码}\n'
        "3. input_data 用接口接受的英文字段名（把中文规则字段翻译成英文，"
        "如 用户名->username、密码->password）；只让被测字段违规，其他字段给合法值。\n"
        "4. expected_status 用接口应拒绝时的状态码（通常 400）。\n"
        "只输出 JSON 数组，不要多余文字。"
    )

    try:
        data = chat_json(user_prompt, system="你只输出 JSON。")
        items = data if isinstance(data, list) else [data]
        cases = [c for c in (_validate_case(it, rules) for it in items) if c is not None]
        # 去重：同样的输入+期望只保留一个
        seen, unique = set(), []
        for c in cases:
            key = (json.dumps(c.input_data, sort_keys=True, ensure_ascii=False), c.expected_status)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        if unique:
            script_source = _render_script(endpoint, unique)
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            script_path = out_dir / f"test_{endpoint.function}.py"
            script_path.write_text(script_source, encoding="utf-8")
            return unique, str(script_path)
    except Exception as exc:
        print(f"[test_generator] LLM 生成用例失败，改用模板兜底：{type(exc).__name__}")

    if fallback:
        return generate(rules, endpoints, out_dir, endpoint_path)
    raise RuntimeError("LLM 生成用例失败，且已关闭兜底")
