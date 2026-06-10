import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout.jsx";
import { fetchAdminEvents, fetchAdminReport, fetchMe } from "../api.js";

const POLL_MS = 3000;
const REPORT_HOURS = 24;

function StatCard({ label, value, hint }) {
  return (
    <div className="report-stat-card">
      <div className="report-stat-label">{label}</div>
      <div className="report-stat-value">{value}</div>
      {hint ? <div className="report-stat-hint">{hint}</div> : null}
    </div>
  );
}

export default function AdminEventsPage() {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [report, setReport] = useState(null);
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
        const [eventsResult, reportResult] = await Promise.all([
          fetchAdminEvents(),
          fetchAdminReport(REPORT_HOURS),
        ]);
        if (!active) return;
        if (!eventsResult.ok) {
          if (eventsResult.status === 401 || eventsResult.status === 403) {
            navigate("/", { replace: true });
            return;
          }
          setError(`請求失敗 (${eventsResult.status})`);
          return;
        }
        setError("");
        setEvents(eventsResult.events);
        if (reportResult.ok) {
          setReport(reportResult.body);
        }
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

  function downloadReport() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `active-defense-report-${new Date().toISOString().slice(0, 19)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const login = report?.login_attempts;
  const audit = report?.audit_events;
  const threat = report?.threat_signals;

  return (
    <DashboardLayout
      username={profile?.username}
      role={profile?.role}
      isAdmin
      breadcrumb="威脅情報監控"
    >
      <div className="admin-events-header">
        <div>
          <h1 className="dashboard-title">威脅情報監控</h1>
          <p className="dashboard-subtitle">
            每 3 秒自動更新。報表統計最近 {REPORT_HOURS} 小時。
          </p>
        </div>
        <button
          type="button"
          className="forgot-submit-btn report-download-btn"
          onClick={downloadReport}
          disabled={!report}
        >
          下載 JSON 報表
        </button>
      </div>
      {error && <p className="status error">{error}</p>}

      {report && (
        <section className="dashboard-section">
          <h2 className="dashboard-section-title">安全數據摘要</h2>
          <div className="report-stat-grid">
            <StatCard label="登入嘗試" value={login?.total ?? 0} hint={`成功 ${login?.successes ?? 0} 次`} />
            <StatCard
              label="MFA 觸發"
              value={login?.by_action?.step_up_mfa ?? 0}
              hint="step_up_mfa"
            />
            <StatCard
              label="封鎖"
              value={(login?.by_action?.block ?? 0) + (login?.by_action?.blocked ?? 0)}
              hint="block / blocked"
            />
            <StatCard label="稽核事件" value={audit?.total ?? 0} />
            <StatCard label="威脅訊號" value={threat?.total ?? 0} />
            <StatCard
              label="平均風險分數"
              value={login?.avg_risk_score ?? "—"}
              hint={login?.by_risk_level ? `high: ${login.by_risk_level.high ?? 0}` : null}
            />
          </div>
        </section>
      )}

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
