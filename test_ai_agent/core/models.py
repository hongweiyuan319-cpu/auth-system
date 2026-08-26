"""
core/models.py —— 数据契约（整个 Agent 的地基）

所有模块共用的数据结构都定义在这里：
- requirements 解析出来的规则 → RequirementRule
- test_generator 生成的用例   → TestCase
- executor 跑完的结果        → TestResult
- debugger 确认的 bug         → BugReport

好处：各模块之间传参类型统一，改数据结构只改这一处。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    """Bug 严重级别（枚举）"""
    BLOCKER = "阻塞"    # 系统完全不可用
    CRITICAL = "严重"   # 核心功能挂了
    MAJOR = "主要"      # 功能不符合需求
    MINOR = "次要"      # 小问题
    TRIVIAL = "轻微"    # 体验问题


@dataclass
class RequirementRule:
    """
    一条从 PRD 解析出来的业务规则。

    例：「用户名长度≥6位」→
        RequirementRule(field="username", description="用户名长度不能少于 6 位", min_len=6)
    """
    field: str                     # 作用字段，如 username / password
    description: str               # 规则的人类可读描述（也用于 bug 单）
    min_len: Optional[int] = None  # 最小长度（长度类规则）
    max_len: Optional[int] = None  # 最大长度
    required: bool = False         # 是否必填（只有解析到「不能为空」才为 True）
    pattern: Optional[str] = None  # 正则规则


@dataclass
class TestCase:
    """
    一个测试用例：给什么输入，期望什么结果，依据哪条规则。
    """
    name: str                      # 用例名，如 "用户名长度为1应注册失败"
    rule: RequirementRule          # 来源规则
    input_data: dict               # 请求/输入数据，如 {"username": "a", "password": "123456"}
    expected_status: int = 200     # 期望的 HTTP 状态码（或函数返回码）
    expected_message: Optional[str] = None  # 期望的返回消息（可选）


@dataclass
class TestResult:
    """
    一条用例的执行结果（executor 产出）。
    """
    case: TestCase                 # 对应的用例
    passed: bool                   # 是否通过
    output: str = ""               # 测试运行输出
    traceback: str = ""            # 失败时的堆栈/报错信息
    duration: float = 0.0          # 耗时（秒）


@dataclass
class BugReport:
    """
    一张 bug 单：debugger 确认是真 bug 后生成，reporter 负责渲染。
    """
    title: str                                     # 标题，如 "用户名未做长度校验"
    file: str                                      # 问题代码文件路径
    line: Optional[int] = None                     # 行号
    severity: Severity = Severity.MAJOR            # 严重级别
    rule: Optional[RequirementRule] = None         # 违反的规则
    reproduction_steps: list = field(default_factory=list)  # 复现步骤
    expected: str = ""                             # 期望行为
    actual: str = ""                               # 实际行为
    suggestion: str = ""                           # 建议修复
    evidence: str = ""                             # 证据（测试输出等）


@dataclass
class FunctionInfo:
    """scanner 扫出来的一个函数。"""
    name: str                                      # 函数名
    file: str                                      # 所在文件路径
    line: int                                      # 起始行号
    params: list = field(default_factory=list)     # 形参列表
    calls: list = field(default_factory=list)      # 函数体内调用的其他函数名


@dataclass
class EndpointInfo:
    """scanner 扫出来的一个 HTTP 接口（被 @app.route 装饰的函数）。"""
    path: str                                      # 路由，如 /api/register
    function: str                                  # 对应处理函数名
    file: str                                      # 所在文件路径
    line: int                                      # 起始行号
    methods: list = field(default_factory=list)    # HTTP 方法，如 ["POST"]
