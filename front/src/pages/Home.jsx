/*
pages/Home.jsx —— 首页
读公告栏（useAuth）：user 有值 = 已登录；没有 = 未登录
提供「退出登录」按钮
*/
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import './auth.css';

function Home() {
  const { user, logout } = useAuth();   // 从公告栏拿当前登录态 + 登出方法

  return (
    <div className="home-page">
      <div className="brand">
        <span className="brand-logo">登</span>
        <span className="brand-name">登录系统</span>
      </div>

      {user ? (
        <>
          <div className="avatar">👤</div>
          <p className="status status-ok">✓ 你已登录</p>
          <p className="subtitle">登录状态已保存，刷新页面也不会丢失</p>
          {/* 不要把 token 明文渲染到页面上（容易被截图/分享泄露），只显示状态就行 */}
          <div className="token">登录凭证已安全保存（不展示具体内容）</div>
          <button onClick={logout}>退出登录</button>
        </>
      ) : (
        <>
          <p className="status">你还没有登录</p>
          <p className="subtitle">登录后即可使用全部功能</p>
          <Link className="primary-link" to="/login">去登录</Link>
        </>
      )}
    </div>
  );
}

export default Home;
