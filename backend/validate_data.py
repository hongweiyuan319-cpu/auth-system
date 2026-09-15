from db import get_connection


def validate_register_input(username,password):

    # 校验类型：用户名和密码都必须是字符串
    # 【为什么要判断】如果不判断，前端传个列表进来（比如 {"username": ["x"]}），
    # 后面 sqlite3 绑定参数时会直接抛 ProgrammingError，接口变成 500 崩溃
    if not isinstance(username, str) or not isinstance(password, str):
        return "用户名和密码格式不正确", 400

    # 校验用户名是否为空
    # 【为什么用 strip()】"   " 这种全是空格的字符串在 Python 里是“真值”，
    # 只写 if not username 拦不住它，会注册出一个“看不见用户名”的账号
    if not username.strip():
        return "用户名不能为空", 400

    # 校验密码是否为空
    if not password:
        return "密码不能为空", 400

    # 校验密码长度是否小于 6 位
    if len(password) < 6:
        return "密码长度不能少于 6 位", 400

    # 校验用户名长度，避免超长字符串撑爆页面/数据库
    if len(username) > 30:
        return "用户名长度不能超过 30 位", 400

    return None, 200


def check_username_exists(username):
    # 用 db.py 里的统一连接，数据库路径不再受“从哪个目录启动”影响
    conn = get_connection()
    cursor=conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE username = ?",(username,)
    )#cursor.execute() 的语法规定：传进去的查询参数必须是一个“容器”（比如元组 Tuple 或列表 List），而不能直接裸写一个变量。
    user = cursor.fetchone()
    conn.close()

    # 原来写成 if/else 两个分支，这里直接返回布尔值，等价但更简洁
    return user is not None