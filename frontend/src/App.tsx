import { type ReactNode, useEffect, useState } from "react";
import { Navigate, Route, BrowserRouter as Router, Routes, useLocation } from "react-router-dom";

import { getMe } from "./api/client";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { NewProjectPage } from "./pages/NewProjectPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ResourceConfigsPage } from "./pages/ResourceConfigsPage";
import { RunHistoryPage } from "./pages/RunHistoryPage";
import { SkillsPage } from "./pages/SkillsPage";
import { ToolConfigsPage } from "./pages/ToolConfigsPage";
import { WorkflowsHubPage } from "./pages/WorkflowsHubPage";
import type { AuthSession, User } from "./types/domain";

function Protected({ user, children }: { user: User | null; children: ReactNode }) {
  const location = useLocation();
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("dd_access_token");
    if (!token) {
      setBooting(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => localStorage.removeItem("dd_access_token"))
      .finally(() => setBooting(false));
  }, []);

  function handleLogin(session: AuthSession) {
    localStorage.setItem("dd_access_token", session.access_token);
    setUser(session.user);
  }

  function handleLogout() {
    localStorage.removeItem("dd_access_token");
    setUser(null);
  }

  if (booting) {
    return <main className="login-stage">加载权限上下文...</main>;
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
        <Route
          path="/*"
          element={
            <Protected user={user}>
              <AppLayout user={user as User} onLogout={handleLogout}>
                <Routes>
                  <Route path="/" element={<Navigate to="/workflows" replace />} />
                  <Route path="/workflows" element={<WorkflowsHubPage />} />
                  <Route path="/scenarios" element={<Navigate to="/workflows" replace />} />
                  <Route path="/workflow-templates" element={<Navigate to="/workflows" replace />} />
                  <Route path="/agent-templates" element={<Navigate to={{ pathname: "/workflows", search: "?tab=agents" }} replace />} />
                  <Route path="/skills" element={<SkillsPage />} />
                  <Route path="/tools" element={<ToolConfigsPage />} />
                  <Route path="/resource-configs" element={<ResourceConfigsPage />} />
                  <Route path="/projects/new" element={<NewProjectPage />} />
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                  <Route path="/projects/:projectId/resources" element={<ProjectDetailPage section="resources" />} />
                  <Route path="/projects/:projectId/outputs" element={<ProjectDetailPage section="outputs" />} />
                  <Route path="/projects/:projectId/runs" element={<ProjectDetailPage section="runs" />} />
                  <Route path="/runs" element={<RunHistoryPage />} />
                </Routes>
              </AppLayout>
            </Protected>
          }
        />
      </Routes>
    </Router>
  );
}
