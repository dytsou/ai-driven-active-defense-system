import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api.js";
import { useKeystroke } from "../hooks/useKeystroke.js";

export default function LoginPage() {
  const navigate = useNavigate();
  const { keyHandlers, getPayload } = useKeystroke();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setStatus("Signing in...");
    try {
      const { body } = await login({
        username,
        password,
        keystroke: getPayload(),
      });
      if (body.status === "success") {
        navigate("/admin/events");
        return;
      }
      if (body.status === "mfa_required" && body.challenge_id) {
        navigate(`/mfa?challenge_id=${encodeURIComponent(body.challenge_id)}`);
        return;
      }
      setStatus(body.message || body.status);
    } catch {
      setStatus("Network error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h1>Active Defense Login</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
            {...keyHandlers}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            {...keyHandlers}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
      {status && <p className="status">{status}</p>}
    </div>
  );
}
