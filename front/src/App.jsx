/*
App.jsx —— 路由地图
作用：访问哪个网址，显示哪个页面
  /login    → 登录页
  /register → 注册页
  /         → 首页（需要登录）
额外加了两道「门卫」：
  RequireAuth      —— 没登录不许进（首页）
  RedirectIfAuthed —— 已经登录了就别再看登录/注册页了
*/
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';

// 门卫一：要求「必须已登录」的页面，用它包一层
// 思路：从公告栏读登录态，有 token 就放行 children，没 token 就跳去登录页
function RequireAuth({ children }) {
  const { user } = useAuth();
  // replace：用「替换」而不是「压栈」跳转，
  // 这样用户点浏览器后退时不会又回到刚刚被拦下的页面
  return user ? children : <Navigate to="/login" replace />;
}

// 门卫二：已经登录的人不该再看到登录 / 注册页，直接送回首页
function RedirectIfAuthed({ children }) {
  const { user } = useAuth();
  return user ? <Navigate to="/" replace /> : children;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<RedirectIfAuthed><Login /></RedirectIfAuthed>} />
      <Route path="/register" element={<RedirectIfAuthed><Register /></RedirectIfAuthed>} />
      <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
      {/* 其他任何路径 → 都跳回首页 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
