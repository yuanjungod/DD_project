import type { PropsWithChildren } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import type { User } from "../types/domain";

type AppLayoutProps = PropsWithChildren<{
  user: User;
  onLogout: () => void;
}>;

export function AppLayout({ user, onLogout, children }: AppLayoutProps) {
  const navigate = useNavigate();

  function logout() {
    onLogout();
    navigate("/login");
  }

  return (
    <div className="console-layout">
      <aside className="sidebar">
        <div className="brand-mark">
          <span>DD</span>
          <div>
            <strong>尽调控制台</strong>
            <small>Agent workflow ops</small>
          </div>
        </div>
        <nav>
          <NavLink to="/scenarios">尽调场景</NavLink>
          <NavLink to="/workflow-templates">流程模板</NavLink>
          <NavLink to="/agent-templates">Agent 配置</NavLink>
          <NavLink to="/skills">Skills 管理</NavLink>
          <NavLink to="/tools">工具管理</NavLink>
          <NavLink to="/resource-configs">资源管理</NavLink>
          <NavLink to="/projects/new">创建应用</NavLink>
          <NavLink to="/projects">场景应用</NavLink>
          <NavLink to="/runs">历史记录</NavLink>
        </nav>
        <div className="user-chip">
          <span>{user.role}</span>
          <strong>{user.name}</strong>
          <small>{user.email}</small>
          <button className="ghost-button" onClick={logout}>
            退出
          </button>
        </div>
      </aside>
      <main className="content-shell">{children}</main>
    </div>
  );
}
