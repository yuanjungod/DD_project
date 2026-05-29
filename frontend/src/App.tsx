import { type ReactNode, useEffect, useState } from "react";
import { Navigate, Route, BrowserRouter as Router, Routes, useLocation } from "react-router-dom";

import { getMe } from "./api/client";
import { clearAccessToken, getAccessToken, setAccessToken } from "./api/auth";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { NewEngagementPage } from "./pages/NewEngagementPage";
import { EngagementDetailPage } from "./pages/EngagementDetailPage";
import { EngagementsPage } from "./pages/EngagementsPage";
import { ResourceConfigsPage } from "./pages/ResourceConfigsPage";
import { RunHistoryPage } from "./pages/RunHistoryPage";
import { SkillsPage } from "./pages/SkillsPage";
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
    const token = getAccessToken();
    if (!token) {
      setBooting(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => clearAccessToken())
      .finally(() => setBooting(false));
  }, []);

  function handleLogin(session: AuthSession) {
    setAccessToken(session.access_token);
    setUser(session.user);
  }

  function handleLogout() {
    clearAccessToken();
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
                  <Route path="/workflow-templates" element={<Navigate to="/workflows" replace />} />
                  <Route path="/agent-templates" element={<Navigate to={{ pathname: "/workflows", search: "?tab=agents" }} replace />} />
                  <Route path="/skills" element={<SkillsPage />} />
                  <Route path="/tools" element={<Navigate to="/resource-configs" replace />} />
                  <Route path="/resource-configs" element={<ResourceConfigsPage />} />
                  <Route path="/engagements/new" element={<NewEngagementPage />} />
                  <Route path="/engagements" element={<EngagementsPage />} />
                  <Route path="/engagements/:engagementId" element={<Navigate to="outputs" replace />} />
                  <Route path="/engagements/:engagementId/outputs" element={<EngagementDetailPage section="outputs" />} />
                  <Route path="/engagements/:engagementId/runs" element={<EngagementDetailPage section="runs" />} />
                  <Route path="/engagements/:engagementId/config" element={<Navigate to="../outputs" replace relative="path" />} />
                  <Route path="/engagements/:engagementId/resources" element={<Navigate to="../outputs" replace relative="path" />} />
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
