"""
db.py —— 数据库公共配置

为什么单独抽一个文件？
    原来的 app.py 和 validate_data.py 里各写了一次 sqlite3.connect("database.db")，
    用的是「相对路径」。相对路径取决于你启动后端时所在的目录：
        在 backend 目录里启动 → 用的是 backend/database.db
        在项目根目录启动     → SQLite 会新建一个空的 database.db（这就是你目录里
                              多出来一个 "database 2.db" 的原因）
    统一放到这里之后，数据库文件永远锁死在 backend/database.db，不管从哪启动都一样。
"""

import os
import sqlite3

# os.path.abspath(__file__) = 当前 db.py 的绝对路径
# os.path.dirname(...)      = 它所在的目录，也就是 backend/
# 两者拼起来 = backend/database.db（绝对路径，不受启动目录影响）
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")


def get_connection():
    """返回一个连到 backend/database.db 的 SQLite 连接"""
    return sqlite3.connect(DB_PATH)
