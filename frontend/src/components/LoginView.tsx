import { useState } from "react";
import type { FormEvent } from "react";

type LoginViewProps = {
  error?: string;
  onSubmit: (username: string, password: string) => Promise<void>;
};

export function LoginView({ error, onSubmit }: LoginViewProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit(username, password);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="app-container" style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "1.5rem" }}>
      <form onSubmit={submit} style={{ width: "min(100%, 420px)", padding: "2rem", border: "1px solid var(--border-subtle)", borderRadius: "16px", background: "var(--bg-card)" }}>
        <p style={{ color: "var(--accent-cyan)", margin: 0 }}>SAT-SA</p>
        <h1 style={{ marginTop: "0.4rem" }}>Sign in</h1>
        <p style={{ color: "var(--text-muted)" }}>Use an account supplied by your system administrator.</p>
        <label htmlFor="username">Username</label>
        <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required style={{ width: "100%", margin: "0.35rem 0 1rem" }} />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required style={{ width: "100%", margin: "0.35rem 0 1rem" }} />
        {error && <p role="alert" style={{ color: "var(--accent-red)" }}>{error}</p>}
        <button type="submit" disabled={submitting} style={{ width: "100%" }}>{submitting ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}
