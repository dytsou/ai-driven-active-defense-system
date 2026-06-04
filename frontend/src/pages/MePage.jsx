import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMe } from "../api.js";
import TopNav from "../components/TopNav.jsx";

function formatCreatedAt(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function MePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [status, setStatus] = useState("Loading profile...");

  useEffect(() => {
    let active = true;

    async function load() {
      const me = await fetchMe();
      if (!active) return;
      if (!me.ok) {
        if (me.status === 401) {
          navigate("/", { replace: true });
          return;
        }
        setStatus(`Request failed (${me.status})`);
        return;
      }
      setProfile(me.body);
      setStatus("");
    }

    load();
    return () => {
      active = false;
    };
  }, [navigate]);

  return (
    <div className="page">
      <TopNav isAuthenticated={Boolean(profile)} isAdmin={profile?.role === "admin"} />
      <h1>My Profile</h1>

      {status && <p className="status">{status}</p>}

      {profile && (
        <div className="profile-card">
          <dl>
            <dt>User ID</dt>
            <dd>{profile.id}</dd>

            <dt>Username</dt>
            <dd>{profile.username}</dd>

            <dt>Email</dt>
            <dd>{profile.email}</dd>

            <dt>Role</dt>
            <dd>{profile.role}</dd>

            <dt>MFA Method</dt>
            <dd>{profile.mfa_method}</dd>

            <dt>Active</dt>
            <dd>{profile.is_active ? "Yes" : "No"}</dd>

            <dt>Created At</dt>
            <dd>{formatCreatedAt(profile.created_at)}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}
