# Python 版本和本地开发保持一致（本地是 3.14.4）。
# 原来写的 3.10 —— 版本不一致会让「本地能跑、容器报错」这类问题变得很难查。
FROM python:3.14-slim

WORKDIR /app

# 先只拷依赖清单：只要它没变，这一层就命中缓存，不用重装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码。database.db / __pycache__ 已被 .dockerignore 排除 ——
# 本机开发库里有真实用户的密码哈希，不该进镜像；
# 容器需要表的话，app.py 会在模块导入时自动 init_db() 建一个空的。
COPY . .

# 暴露 Flask 运行的 5000 端口
EXPOSE 5000

# 启动命令：
#   app:app            = 模块 app.py 里的 Flask 实例 app
#   --workers 1        = 只开 1 个进程。SQLite 是「文件级写锁」，
#                        多个 worker 同时写会报 "database is locked"，
#                        所以这里用单进程 + 多线程（--threads）来扛并发
#   --access-logfile - = 访问日志打到标准输出，docker logs 里能直接看见
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "app:app"]

# 注意：这里不要再写 gunicorn==x.y.z 这类行！
#   Dockerfile 不是 requirements.txt，每一行都会被当成 Docker 指令来解析，
#   写包名会让构建直接报 “unknown instruction” 而中断。
#   gunicorn 的版本已经在 requirements.txt 里钉好了，上面那句
#   RUN pip install -r requirements.txt 会把它装进来。