/*
pages/Login.jsx —— 登录页
流程：填账号密码 → 调后端登录接口 → 拿到 token → 交给 AuthContext 存起来 → 跳回首页
*/
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';   // useNavigate：跳转工具；Link：跳转链接
import { login } from '../api/auth';                    // 后端登录接口（发请求拿 token）
import { useAuth } from '../context/AuthContext';       // 从公告栏拿「存 token」的方法
import './auth.css';                                    // 页面样式

function Login() {
  // ① 表单三个状态：账号、密码、错误提示
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const navigate = useNavigate();                        // ② 跳转工具（跳去别的页面）
  const { login: saveToken } = useAuth();                // ③ 从公告栏拿 login 方法，改名叫 saveToken（避免和上面的接口 login 撞名）

  // ④ 点「登录」按钮时触发
  const handleSubmit = async (e) => {
    e.preventDefault();                                  // 阻止表单默认的「刷新页面」行为
    setError('');                                        // 先清掉上次的错误提示
    try {
      const res = await login(username, password);       // 1. 调后端接口，成功后拿到响应（里面有 token）
      saveToken(res.data.access_token);                  // 2. 把 token 交给 AuthContext 存进 localStorage + 内存
      navigate('/');                                     // 3. 跳回首页
    } catch (err) {
      // 失败：显示后端返回的错误原因（request.js 响应拦截器统一抛下来的）
      setError(err.response?.data?.message || '登录失败，请重试');
    }
  };

  return (
    <div className="auth-page">
      <div className="brand">
        <span className="brand-logo">登</span>
        <span className="brand-name">登录系统</span>
      </div>
      <h2>登录</h2>
      <p className="subtitle">登录你的账户以继续</p>
      {error && <p className="error">{error}</p>}
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit">登录</button>
      </form>
      <p className="switch">还没有账号？<Link to="/register">立即注册</Link></p>
    </div>
  );
}

export default Login;
