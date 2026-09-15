import requests
BASE_URL = "http://127.0.0.1:5000/api"#URL是网址，5000是设置的端口号，127.0.0.1 泛指所有电脑的本地

def test_register_and_login():
    print(" --- automatic prots testing starts --- ")

    # 测试数据
    test_user={"username":"test_student","password":"secure_password123"} #请求数据
    # () 元组 (Tuple)：用于存放不能修改的数据
    # [] 列表 (List)：用于存放可以随时修改的多个数据
    # {} 字典 (Dict)：用于存放键值对（Key-Value，像查字典一样用名字找数据）

    # 1. 测试注册接口(POST /api/register)
    print("\n[1] testing register ports")
    res_reg = requests.post(f"{BASE_URL}/register",json=test_user)# 向python后端发送一个HTTP的POST请求，去注册一个新用户
   
        # post(a, b): 
            # a = 请求的网址URL, 告诉后端要把数据发到哪里；
                # f"{BASE_URL}/register"：利用 f-string 把基础网址和后缀拼接起来
            # b = 要发送的数据，告诉后端这次发过去具体包含什么内容
                # # json=test_user：把前面定义好的用户字典数据（包含账号和密码）自动转换成 JSON 格式，作为请求的内容发送给后端
            # post() 本身是在向服务器“提交数据”或“发送数据”
        # requests.方法名(): 
            # requests 是 Python 里一个专门用来发送网络请求的工具库
            # .() 里的方法代表请求的动作（比如 .get() 是获取数据，.post() 是提交/发送数据）
        # request.post()产物：
            # res_reg.status_code（状态码）：
                # 200表示成功
                # 201表示创建成功
                # 400/401表示客户端出错
                # 500表示服务器崩了
            # res_reg.json()（响应数据）：
                # 后端返回的具体内容（通常是 Python 字典格式）
                # 比如后端在代码里写的 {"message": "注册成功"}
            # res_reg.text（原始文本）：
                # 服务器返回的原始字符串内容
            # res_reg.headers（响应头）：
                # 服务器的一些元数据信息（比如服务器类型、响应的数据格式等）
    print(f"状态码: {res_reg.status_code}")
    print(f"响应内容: {res_reg.json()}")
    # 重复运行这个脚本时，用户已经存在，注册会返回 400「该用户名已被注册」
    # 这是正常现象，不影响后面用这个账号做登录测试
    if res_reg.status_code not in (200, 400):
        print("❌ 注册接口异常，请检查后端是否已启动")
        return

    # 2. 测试登录接口 (POST /api/login)
    print("\n[2] 正在测试【登录接口】...")
    res_log = requests.post(f"{BASE_URL}/login", json=test_user)
    print(f"状态码: {res_log.status_code}")
    print(f"响应内容: {res_log.json()}")

    # 3. 测试Token获取
    token = res_log.json().get("access_token")
    # login_res.json()：把服务器返回的响应内容转换成 JSON 格式（通常是一个字典）
    # .get("access_token")：从这个字典里，把键名为 "access_token" 的那串核心字符串拿出来，赋值给变量 token
    # ⚠️ 后端返回的字段名是 access_token，不是 token！
    #    原来写成 .get("token") 永远拿到 None，后面拼出来的请求头是 "Bearer None"，必然 401
    print("拿到的通行证：", token)
    if not token:
        print("❌ 没拿到 token，后面的【机密接口】测试一定失败，请先检查用户名/密码是否正确")
        return

    # 4. 测试Token访问机密接口
    headers = {
    "Authorization": f"Bearer {token}"
}#组装请求头，按照规范把 Token 塞进
    protected_res = requests.get(f"{BASE_URL}/user/profile", headers=headers)
    print("访问机密接口结果：", protected_res.json())

    print("\n--- 测试结束 ---")

if __name__ == "__main__":
    test_register_and_login()