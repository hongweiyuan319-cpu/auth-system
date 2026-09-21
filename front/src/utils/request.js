/*
Request 就是前端当想找后端要数据，或者把用户填的数据交给后端时，派出的“快递员”或“信使”
设计要素：
    1. URL
        1.1 告诉后端你想访问哪个接口
    2. Method
        2.1 GET
        2.2 POST
        2.3 PUT/PATCH
        2.4 DELET
    3. Params / Data
        3.1 告诉后端具体的操作细节
        3.2 GET 请求通常把参数拼在 URL 后面（叫 Query 参数，例如 ?id=1）
        3.3 POST/PUT 请求把参数放在请求体里（叫 Body 参数，通常是 JSON 格式）
    4. Headers
        4.1 带上 Token,证明用户已经登录了，后端才允许你获取私密数据

后端接口设置：
    1. register：
        1.1 URL：http://localhost:5000/api/register
        1.2 method：POST
        1.3 role：创建账号
        1.4 request body：JSON
    2. login
        2.1 URL：http://localhost:5000/api/login
        2.2 method：POST
        2.3 role：登录，拿 token
    3. check token
        3.1 URL：http://localhost:5000/api/user/profile
        3.2 method：GET
        3.3 role：带 token 查当前用户
*/


// axios实例：
    //定义： 配置好的、专门给后端服务的请求器
    //意义：如果不创建实例、直接每次接口都要重复写，创建实例的好处 = 一次性配好，到处复用：
        //1. 地址只写一次（baseURL）
        //2. token 自动带
        //3. 错误统一处理
    //创建逻辑：
        //1. 引入 axios
import axios from 'axios';

        //2. 创建实例，顺便把"通用设置"写好
const request = axios.create({
  // baseURL 留空 = 用「相对路径」，请求会发到当前页面所在的域名下。
  // 为什么不写死 http://127.0.0.1:5000 ？
  //   1. 写死的地址会被 vite 编译进静态 JS。测试工程师从 http://服务器IP:8080
  //      打开页面时，浏览器会去请求「他自己电脑」的 5000 端口 —— 那里什么都没有，
  //      所有请求必然失败。
  //   2. nginx 里配的 location /api/ 反向代理也永远不会被命中，等于白配。
  // 留空之后，请求形如 /api/login，由谁来转发取决于环境：
  //   本地开发 → vite.config.js 里的 server.proxy 转发到 127.0.0.1:5000
  //   Docker   → nginx.conf 里的 location /api/ 转发到后端容器
  // 同一份前端代码两种环境都能跑，不用为了环境改代码。
  baseURL: '',
  timeout: 10000,                     // 超过 10 秒没响应就报错
});

        //3. 导出
export default request;

//请求拦截器
    //定义： 在"每次请求发出之前"自动执行的代码，自动把 token 从 localStorage 取出来塞进请求头，然后放行。让所有接口都不用自己手动带 token。
    //意义：一次性写好，所有请求自动带 token，不用每个接口操心；如果不写拦截器，你每个需要 token 的请求都要手动写。
    //构建逻辑
        //0. 给实例挂一个"请求拦截器"
        //1. 取 token
        //2. 放进去
        //3. 放行


//request: 刚刚创建的axios实例
//interception：这个实例的所有"拦截器"
//request：其中的"请求拦截器"
//.use(...) ："注册"处理函数，告诉axios，记住这两个函数，以后每次发请求时自动帮我执行
request.interceptors.request.use(
    (config)=>{
        //① 取：从 localStorage 里把登录时存的 token 拿出来
        const token = localStorage.getItem('token')
        // ② 放：如果 token 存在，就把它塞进请求头
        if (token){
            config.headers.Authorization = `Bearer ${token}` //axios自动会给创建的函数配置一个headers，但是里面是空的，然后我们在新增一个Authorizaton再把token放进去
        }
        // ③ 放行：处理完必须 return config，否则请求发不出去
        return config;
    },
    // 第二个参数：万一在"准备阶段"就出错了，走这里（先了解，很少用到）
    (error) => Promise.reject(error)//Promise.reject(error)：这个错误"标记为失败"，继续往下抛
                                    //为什么要抛？ 因为错误不能在这吞掉——要传给调用方（页面的 .catch）去处理，本质上是后端的错误打包到error里面向上传播
);

//响应拦截器
    //定义： 在"后端响应返回之后、交给页面之前"自动执行的代码，后端回应后，成功就直接放行；失败就统一处理——401 自动登出跳登录页，其他错误原样抛给页面去显示。
    //意义：
        //1. 后端报错时，每个接口返回的"错误长相"不一样，如果每个页面都自己处理，重复又乱。响应拦截器可以在错误到达页面之前统一拦下来处理。
        //2. token 过期了，后端返回 401。响应拦截器里统一做：清掉本地 token → 跳回登录页
    //构建逻辑
        //1. 请求成功放行
        //2. 请求失败判断状态码再向下抛
request.interceptors.response.use(
  // 参数1：请求成功（后端返回了 2xx）时执行
  (response) => {
    return response;   // 成功：原样放行，页面拿到数据
  },

  // 参数2：请求失败（后端返回 4xx/5xx）时执行
  (error) => {
    // 重点：如果状态码是 401（未登录 / token 失效）
    if (error.response && error.response.status === 401) {
    //error.response看这个错误是不是后端返回的，&&表示若前半段成立再看后面，error.response.statues === 401看状态码判断是不是未登录
      localStorage.removeItem('token');   // 清掉实效的本地 token
      window.location.href = '/login';    // 跳回登录页
    }
    // 其他错误：原样抛下去，让页面的 .catch 用 err.response.data.message 显示原因
    return Promise.reject(error);
  }
);
