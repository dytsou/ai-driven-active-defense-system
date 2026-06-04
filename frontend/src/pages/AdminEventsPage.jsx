import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchAdminEvents, fetchMe } from "../api.js";
import TopNav from "../components/TopNav.jsx";

const POLL_MS = 3000;

export default function AdminEventsPage() {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
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
          setError(`Request failed (${result.status})`);
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
    <div className="page-wide">
      <TopNav isAuthenticated isAdmin />
      <h1>Threat Intelligence Monitor</h1>
      <p>Polling every 3 seconds.</p>
      {error && <p className="status error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Type</th>
            <th>User</th>
            <th>IP</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {events.length === 0 ? (
            <tr>
              <td colSpan={5}>{error ? "—" : "No events"}</td>
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
  );
}
