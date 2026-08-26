"""
core/scanner.py —— 第 3 步：扫描被测代码（用 AST）

输入：被测代码路径（文件或目录，如 ../qa_ai_agent/backend）
输出：(functions, endpoints)
      functions  -> list[FunctionInfo]   所有函数
      endpoints  -> list[EndpointInfo]   所有 HTTP 接口（被 @app.route 装饰）

对应测试工程师的动作：先翻一遍代码，搞清楚"被测对象是谁、入口在哪"。
用 AST（把代码解析成结构树）而不是正则：注释/字符串里的"def xxx"不会被误认成真函数。
"""
import ast
from pathlib import Path

from core.models import FunctionInfo, EndpointInfo


def _parse_file(file_path: Path):
    """解析一个 .py 文件，收集里面的函数和接口。"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return [], []   # 不是合法的 Python（或解析失败），跳过

    functions: list[FunctionInfo] = []
    endpoints: list[EndpointInfo] = []

    for node in ast.walk(tree):          # 遍历整棵树的所有节点
        if not isinstance(node, ast.FunctionDef):
            continue                     # 只关心"函数定义"节点

        # ── 收集函数：名字 / 参数 / 调用了谁 ──
        params = [a.arg for a in node.args.args]
        calls = []
        for sub in ast.walk(node):       # 在函数体内再走一遍
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                if sub.func.id not in calls:
                    calls.append(sub.func.id)

        functions.append(FunctionInfo(
            name=node.name,
            file=str(file_path),
            line=node.lineno,
            params=params,
            calls=calls,
        ))

        # ── 判断是不是 Flask 接口：有没有 @app.route("...") 装饰器 ──
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            if dec.func.attr != "route":           # 只认 @app.route
                continue
            # 路由路径：@app.route("/api/register")
            first_arg = dec.args[0] if dec.args else None
            path = first_arg.value if isinstance(first_arg, ast.Constant) else "?"
            # methods=["POST", ...]
            methods = []
            for kw in dec.keywords:
                if kw.arg == "methods" and isinstance(kw.value, ast.List):
                    for elt in kw.value.elts:
                        if isinstance(elt, ast.Constant):
                            methods.append(elt.value)
            endpoints.append(EndpointInfo(
                path=path,
                methods=methods,
                function=node.name,
                file=str(file_path),
                line=node.lineno,
            ))

    return functions, endpoints


def scan(target_path: str):
    """
    扫描目标路径（文件或目录），返回 (functions, endpoints)。
    目录会递归查找所有 .py 文件。
    """
    target = Path(target_path)
    functions: list[FunctionInfo] = []
    endpoints: list[EndpointInfo] = []

    py_files = [target] if target.is_file() else list(target.rglob("*.py"))
    for f in py_files:
        funcs, eps = _parse_file(f)
        functions.extend(funcs)
        endpoints.extend(eps)

    return functions, endpoints
