import type { PropsWithChildren } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import type { User } from "../types/domain";

type AppLayoutProps = PropsWithChildren<{
  user: User;
  onLogout: () => void;
}>;

/** true for /engagements and /engagements/:id, but not /engagements/new. */
function isEngagementsSectionActive(pathname: string): boolean {
  if (pathname === "/engagements") {
    return true;
  }
  if (!pathname.startsWith("/engagements/")) {
    return false;
  }
  return !pathname.startsWith("/engagements/new");
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
          <span>HP</span>
          <div>
            <strong>Harness 控制台</strong>
            <small>Agent orchestration</small>
          </div>
        </div>
        <nav>
          <NavLink to="/skills">Skills 管理</NavLink>
          <NavLink to="/resource-configs">平台资源</NavLink>
          <NavLink to="/workflows">Agent和工作流模板</NavLink>
          <NavLink to="/engagements/new">创建 Engagement</NavLink>
          <NavLink
            to="/engagements"
            aria-current={isEngagementsSectionActive(location.pathname) ? "page" : undefined}
            className={() => (isEngagementsSectionActive(location.pathname) ? "active" : undefined)}
          >
            Engagements
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
