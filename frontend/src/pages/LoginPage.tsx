import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "../api/client";
import type { AuthSession } from "../types/domain";

type LoginPageProps = {
  onLogin: (session: AuthSession) => void;
};

const defaultLoginEmail = import.meta.env.VITE_DEFAULT_LOGIN_EMAIL || "";
const defaultLoginPassword = import.meta.env.VITE_DEFAULT_LOGIN_PASSWORD || "";
const showDevLoginHints = import.meta.env.VITE_SHOW_DEV_LOGIN_HINTS === "true";

export function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState(defaultLoginEmail);
  const [password, setPassword] = useState(defaultLoginPassword);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const session = await login({ email, password });
      onLogin(session);
      navigate("/workflows");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-stage">
      <section className="login-panel">
        <p className="eyebrow">Harness Agent Orchestration</p>
        <h1>登录 Harness 平台</h1>
        <p className="muted">
          {showDevLoginHints && defaultLoginEmail && defaultLoginPassword
            ? `开发默认账号：${defaultLoginEmail} / ${defaultLoginPassword}。管理员可查看全部 Engagement，分析师可创建并运行 Engagement，只读用户只能查看。`
            : "使用分配的账号登录。支持配置 Agent 工作流模板与 Engagement 实例。"}
        </p>
        {error ? <div className="error">{error}</div> : null}
        <form className="form" onSubmit={handleSubmit}>
          <label>
            邮箱
            <input value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            密码
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button disabled={loading}>{loading ? "登录中..." : "登录"}</button>
        </form>
      </section>
    </main>
  );
}
