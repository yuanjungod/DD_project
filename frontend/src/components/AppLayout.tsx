import type { PropsWithChildren } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import type { User } from "../types/domain";

type AppLayoutProps = PropsWithChildren<{
  user: User;
  onLogout: () => void;
}>;

/** true for /projects and /projects/:id, but not /projects/new (prefix match would otherwise double-highlight). */
function isProjectsSectionActive(pathname: string): boolean {
  if (pathname === "/projects") {
    return true;
  }
  if (!pathname.startsWith("/projects/")) {
    return false;
  }
  return !pathname.startsWith("/projects/new");
}

export function AppLayout({ user, onLogout, children }: AppLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();

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
          <NavLink to="/skills">Skills 管理</NavLink>
          <NavLink to="/tools">工具管理</NavLink>
          <NavLink to="/resource-configs">平台资源</NavLink>
          <NavLink to="/workflows">场景与流程</NavLink>
          <NavLink to="/projects/new">创建应用</NavLink>
          <NavLink
            to="/projects"
            aria-current={isProjectsSectionActive(location.pathname) ? "page" : undefined}
            className={() => (isProjectsSectionActive(location.pathname) ? "active" : undefined)}
          >
            场景应用
          </NavLink>
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
