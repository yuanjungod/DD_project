import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "../api/client";
import type { AuthSession } from "../types/domain";

type LoginPageProps = {
  onLogin: (session: AuthSession) => void;
};

export function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const session = await login({ email, password });
      onLogin(session);
      navigate("/scenarios");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-stage">
      <section className="login-panel">
        <p className="eyebrow">Permissioned Due Diligence</p>
        <h1>登录尽调平台</h1>
        <p className="muted">默认账号：admin@example.com / admin123。管理员可查看全部项目，分析师可创建并运行项目，只读用户只能查看。</p>
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
