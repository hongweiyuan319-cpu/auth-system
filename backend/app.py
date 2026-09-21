import os
import sqlite3 
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS  # 允许前端跨域访问
from werkzeug.security import check_password_hash, generate_password_hash #引入哈希
from validate_data import validate_register_input
from validate_data import check_username_exists
from db import get_connection  # 统一的数据库连接（固定指向 backend/database.db）
import jwt
import datetime


# 从项目根目录的 .env 读取环境变量（backend/ 的上一级）。
# 用绝对路径而不是相对路径，保证不管从哪个目录启动 app.py，找到的都是同一个 .env。
# load_dotenv 默认「不覆盖」已存在的环境变量 —— 这正是我们想要的：
# 部署时用 export 注入的正式值，优先级高于本地 .env 里的开发值。
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


#1. 开启跨域
app = Flask(__name__) #创建一个Flask网页服务器的实例，用__name__和该文件捆绑
CORS(app) #给刚刚创建的 app 跨域，此时这个后端变成了“允许来自任何网址、任何前端的跨域请求”的状态


#2. 初始化 SQLite 数据库（自动建表）
def init_db():
    conn = get_connection() #创建：在SQLite中，创建数据库和连接数据库是同一个动作。统一走 db.py，数据库固定在 backend/database.db
    cursor = conn.cursor()#之前的conn是连接数据库，现在的cursor是相当于申请增删改查操作权限
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
            )
        """)#创建一个叫user的表，如果表已经存在，就不要重复创建(第一列叫ID，存整数，作为唯一主键，并且自动递增；第二列叫username，存文本，不能为空；第三列叫password，存文本，不能为空)

    # 给 username 补一个唯一索引：即使 users 表是之前建的（没写 UNIQUE），这句也能补上约束。
    # 这样「同一用户名注册两次」在数据库层面就会被拦住，不再只靠 check_username_exists 的「先查后插」
    # （先查后插在并发/双击提交时可能漏网，唯一索引才是最后一道防线）
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    except sqlite3.IntegrityError:
        # 说明旧数据里已经有重复用户名了，需要先把重复数据清理掉才能加上约束
        print("⚠️ users 表里已存在重复用户名，无法创建唯一索引，请先清理重复数据")

    conn.commit() #提交并保存
    conn.close() #关闭

#功能1: 存数据，当填入账号密码并且点击注册后，后端要把数据写入数据库
#功能2: 查数据，登录的时候，后端要进入数据库核对数据


#3. 注册接口(POST)
@app.route("/api/register",methods=["POST"]) #当客户端向服务器发送请求，访问/api/register路径时，会触发下面定义的函数来处理，只接受 POST 请求：
#客户端是发起请求的一方，服务器是响应请求的一方
def register():
    data = request.get_json(silent=True) #从request里面拿到JSON数据
    # silent=True：请求体不是合法 JSON 时返回 None，而不是抛 415/400 的 HTML 错误页，
    # 这样前端拿到的依然是统一的 JSON 错误提示
    if not isinstance(data, dict):
        return jsonify({"message": "请求内容不能为空，请传入JSON数据", "code": 400}), 400
    username = data.get("username")
    password = data.get("password")

    # 统一去掉首尾空格：否则 "  alice" 和 "alice" 会被当成两个不同的账号
    # （登录接口里做了同样的处理，两边规则必须一致）
    if isinstance(username, str):
        username = username.strip()
    if isinstance(password, str):
        password = password.strip()


    error_message, status_code = validate_register_input(username, password)
    if error_message:
        return jsonify({"message": error_message, "code": status_code}), status_code

    if check_username_exists(username):
        return jsonify({"message": "该用户名已被注册", "code": 400}), 400


    hashed_password = generate_password_hash(password)## 存入数据库的是 hashed_password，而不是明文 password

    conn = get_connection()
    cursor = conn.cursor()

    try:#尝试执行
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username,hashed_password),
        )#把新用户的 username 和 password 写入数据库的 users 表中
        conn.commit()
    except sqlite3.IntegrityError:#命中 username 的 UNIQUE 唯一约束
        return(
            jsonify({"message": "该用户名已被注册", "code": 400}),400,
        )#并发或双击提交时「先查后插」可能漏网，这里靠数据库的唯一约束兜底
    except Exception as e:#其他异常（比如数据库被锁、磁盘写满）
        app.logger.exception("注册失败")#把详细报错写进后端日志，方便自己排查
        return(
            jsonify({"message": "注册失败，请稍后重试", "code": 500}),500,
        )#注意：不要把 str(e) 返回给客户端，否则会泄露表结构等内部信息
    finally:
        conn.close()

    return jsonify({"message": "注册成功", "code": 200}), 200 #这里只会在try完成之后执行，二expect发生不执行

# jsonify是Flask框架的一个工具函数，专门用来把Python的数据转换成JSON格式，并打包冲HTTP响应发送给客户端
# jsonify({...}), 200
    # jsonify({"message": "注册成功", "code": 200})：
        # 括号里是一个Python字典，包含了想告诉客户端的信息，jsonify 会把它转换成标准的 JSON 字符串（前后端数据交互的通用语言）
        # 内层200是给代码逻辑看的，代表代码的功能本身实现了
    # , 200：
        # 这是 HTTP 状态码。200 代表请求成功
        # 外层200给浏览器看，表示网络请求本身是通畅的

# SQLite
    # KEY表示列名，如 username、password
    # PRIMARY KEY: 数据的唯一身份证号。用来标识某一行数据绝不重复（比如每个用户的 ID），不能为空
    # AUTOINCREMENT: 让数据库自动编号。每插入一条新数据，这个数字自动加 1（比如 1、2、3...），不用手动输入


# 4. 登录接口(POST)
@app.route("/api/login",methods=["POST"])
def login():
    data = request.get_json(silent=True) #把客户端发来的JSON格式数据读取后转换成Python字典，方便后续使用
    if not isinstance(data, dict):
        return jsonify({"message": "请求内容不能为空，请传入JSON数据", "code": 400}), 400
    username = data.get("username")
    password = data.get("password")

    # 类型不对（传了列表/数字等）直接判为登录失败，避免 SQLite 报错变成 500
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"message": "用户名和密码格式不正确", "code": 400}), 400

    # 登录和注册必须用同一套「去空格」规则，否则会出现「密码明明是对的却登录失败」
    username = username.strip()
    password = password.strip()

    conn = get_connection()

    conn.row_factory = sqlite3.Row   # 让查询结果支持用列名取值

    
    cursor = conn.cursor()
    # 【关键修改】只根据 username 去数据库把这个人的信息全查出来
    cursor.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    )
# SELECT * FROM users：从users里面查询并获取符合条件的所有数据
# WHERE username = ? AND password = ? ：查询条件是——用户名和密码必须同时与传入的变量（username, password）相匹配
# WHERE本身必须要求找到符合要求的必须是同一“行”
# ？赋值顺序按照出现顺序对应
# WHERE username = ? AND password = ? 中的username和password都是列名
    user = cursor.fetchone() #获取查询结果，查询结果可能有很多条，但是fetchone只看第一条
    conn.close()

# execute：在数据库内部生成了一个临时的“查询结果集”
# fetchone：从这个临时结果集里抓取第一条数据
# close（关闭连接）：这个临时结果集和操作通道一起被销毁，释放内存

    if user and check_password_hash(user["password"], password):
        access_token = generate_token(username)
    # user 的结构是：(id, username, password_hash)
        return jsonify({"message": "登录成功", "code": 200,"access_token" : access_token,}), 200
    else:
        return jsonify({"message":"登录失败", "code":400}),400


# 5. JWT生成Token
# 新增服务器私钥（签名密钥）
# 值写在项目根目录的 .env 里（已被 .gitignore 忽略），由上面的 load_dotenv() 读进来。
# 长度至少 32 字节是 HS256 的安全下限，太短 PyJWT 会报 InsecureKeyLengthWarning。
#
# 为什么不再写兜底默认值？
#   以前这里写的是 os.environ.get("AUTH_SECRET_KEY", "dev_only_secret_key_...")，
#   那个默认值已经随代码提交到了 GitHub —— 等于把签名密钥公开了。
#   任何人拿到那串字符，都能自己签出一个「合法」token 冒充任意用户登录，
#   而且服务端无法分辨（JWT 无状态，只验签名不查库）。
#   所以改成「读不到就直接启动失败」：
#       忘设 = 服务起不来（你立刻就会发现）
#   而不是 忘设 = 悄悄用公开密钥（你可能永远发现不了）
SECRET_KEY = os.environ.get("AUTH_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "缺少环境变量 AUTH_SECRET_KEY，服务拒绝启动。\n"
        "请先准备配置文件：\n"
        "    cp .env.example .env        # 在项目根目录执行\n"
        "    python -c \"import secrets; print(secrets.token_hex(32))\"  # 生成密钥填进去\n"
    )
# HTTPS加密逻辑：
    # 默认加密：之前的临时密钥是一次性的，用完就销毁
    # 长期密钥：服务器用长期密钥配合算法加密计算生成 Token，然后Token本身有过期时间，在过期时间内，服务器不用存Token，只需要用本地的产期密钥用算法核算即可

def generate_token(username):
    """
    接收用户名，生成并返回一个 JWT 通行证字符串
    """
    payload = {
        "username": username,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2) # 2小时后过期
    }#这段代码在打包生成Token需要包含的核心数据
    # "username": username：在记录是谁登录的，方便服务器以后通过这个 Token 知道当前操作的用户是谁
    # "exp": ...：设置token的过期时间，过这个时间之后Token会自动失效，用户需要重登录

    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


# 6. 检验Token
def verify_request_token():
    auth_header = request.headers.get("Authorization")#获取客户端（浏览器）发来的请求头中的认证信息
    # request.headers：获取这次请求的所有头部（Header）信息
    # .get("Authorization")：从中提取名为 "Authorization" 的字段。这个字段通常装着用户的“通行证”（Token），也就是前端发请求时用来证明自己身份的关键凭证。
    if not auth_header or not auth_header.startswith("Bearer "): #如果Token不存在或者Token格式不标准（Authorization的标准格式是：Bearer + Token）
        return None, "缺少有效通行证"

    token = auth_header.split(" ")[1]#以空格为界限，把字符串切开取第二个元素（Bearer + Token 中取 Token）
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])#用长期密钥（SECRET_KEY）去检查 Token 是否合法：
        return payload.get("username"), None # 成功：返回用户名和空错误
    except jwt.ExpiredSignatureError:
        return None, "通行证已过期"
    except jwt.InvalidTokenError:
        return None, "无效的通行证"


@app.route("/api/user/profile", methods=["GET"])
def get_user_profile():#检验开始
    current_user, error_msg = verify_request_token()
    if error_msg:
        return jsonify({"message": error_msg, "code": 401}), 401
    return jsonify(
      {"message": f"成功获取 {current_user} 的个人信息", "code": 200}
  ), 200


# ⚠️ 入口必须放在文件最末尾！否则服务器一启动就卡住，后面的函数（如 generate_token）根本来不及定义
if __name__ == "__main__":#判断当前文件是不是被直接运行的。如果是，才执行下面的代码。
    init_db()
    print("后端服务器已启动，正在监听 http://127.0.0.1:5000 ...")
    app.run(debug=True, port=5000)#正式启动 Web 服务器，监听本地的 5000 端口，等待前端发请求进来

#debug=True：开启调试模式。代码修改保存后，服务器会自动重启，不需要手动重启；如果代码报错，网页上会直接显示详细的错误信息，方便排查问题。
#port=5000：指定服务器运行的端口号。
    #意思是让后端程序在电脑的 5000 端口上监听请求
    #前端访问时也需要把请求发到这个端口。
    #5000是Flask的默认端口，类似于HTTP默认的80端口