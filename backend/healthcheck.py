"""
healthcheck.py —— 给 Docker 用的健康检查探针

为什么单独写一个文件，而不是把这段逻辑塞进 docker-compose.test.yml 的一行命令里？
    因为这段判断要区分「连不上」和「返回 4xx」两种情况，
    写成一行 shell 命令需要大量转义，又长又难读，还容易写错。

判定标准：
    能收到任意 HTTP 响应（包括我们预期中的 401）→ 服务已经活着 → 退出码 0
    连接被拒 / 超时                              → 还没起来     → 退出码 1

为什么不用「端口能不能连上」来判断（更简单的做法）？
    因为 gunicorn 会**先绑定监听端口，再加载应用代码**。
    端口刚通的那一刻，Flask 可能还没准备好，这时判为健康，前端就会在
    后端真正可用之前启动，用户首屏请求会撞上 502。
    所以必须实际发一个 HTTP 请求，才能确认应用层真的就绪。
"""

import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:5000/api/user/profile"

try:
    urllib.request.urlopen(URL, timeout=2)
except urllib.error.HTTPError:
    # 收到 HTTP 响应（这里是预期的 401「缺少有效通行证」）——
    # 说明 Flask 已经能正常处理请求了，这就是健康。
    sys.exit(0)
except Exception:
    # 连接被拒、超时等 → 说明还没起来。
    sys.exit(1)

# 理论上走不到这里（该接口不带 token 一定 401），
# 但万一将来接口行为变了（比如它开始返回 200），收到响应依然算健康。
sys.exit(0)
