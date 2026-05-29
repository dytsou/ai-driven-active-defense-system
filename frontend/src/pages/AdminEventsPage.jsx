import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAdminEvents } from "../api.js";

const POLL_MS = 3000;

export default function AdminEventsPage() {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const inFlightRef = useRef(false);

  useEffect(() => {
    let active = true;

    async function refresh() {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        const result = await fetchAdminEvents();
        if (!active) return;
        if (!result.ok) {
          setError(`Unauthorized (${result.status})`);
          setEvents([]);
          return;
        }
        setError("");
        setEvents(result.events);
      } finally {
        inFlightRef.current = false;
      }
    }

    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="page-wide">
      <h1>Threat Intelligence Monitor</h1>
      <p>
        Polling every 3 seconds. <Link to="/">Back to login</Link>
      </p>
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
