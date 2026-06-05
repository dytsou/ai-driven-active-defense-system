import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout.jsx";
import { fetchAdminEvents, fetchMe } from "../api.js";

const POLL_MS = 3000;

export default function AdminEventsPage() {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const inFlightRef = useRef(false);

  useEffect(() => {
    let active = true;
    let timer;

    async function refresh() {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        const result = await fetchAdminEvents();
        if (!active) return;
        if (!result.ok) {
          if (result.status === 401 || result.status === 403) {
            navigate("/", { replace: true });
            return;
          }
          setError(`請求失敗 (${result.status})`);
          return;
        }
        setError("");
        setEvents(result.events);
      } finally {
        inFlightRef.current = false;
      }
    }

    async function start() {
      const me = await fetchMe();
      if (!active) return;
      if (!me.ok || me.body?.role !== "admin") {
        navigate("/", { replace: true });
        return;
      }
      setProfile(me.body);
      await refresh();
      if (!active) return;
      timer = setInterval(refresh, POLL_MS);
    }

    start();

    return () => {
      active = false;
      if (timer) clearInterval(timer);
    };
  }, [navigate]);

  return (
    <DashboardLayout
      username={profile?.username}
      role={profile?.role}
      isAdmin
      breadcrumb="威脅情報監控"
    >
      <h1 className="dashboard-title">威脅情報監控</h1>
      <p className="dashboard-subtitle">每 3 秒自動更新登入與風險事件。</p>
      {error && <p className="status error">{error}</p>}

      <div className="dashboard-panel">
        <table>
          <thead>
            <tr>
              <th>時間</th>
              <th>類型</th>
              <th>使用者</th>
              <th>IP</th>
              <th>詳細資料</th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 ? (
              <tr>
                <td colSpan={5}>{error ? "—" : "目前沒有事件"}</td>
              </tr>
            ) : (
              events.map((event) => (
                <tr key={event.id}>
                  <td>{event.created_at || ""}</td>
                  <td>{event.event_type}</td>
                  <td>{event.actor_username || ""}</td>
                  <td>{event.ip_address || ""}</td>
                  <td>
                    <code>{JSON.stringify(event.payload || {})}</code>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </DashboardLayout>
  );
}
