import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DashboardLayout from "../components/DashboardLayout.jsx";
import { fetchAdminEvents, fetchAdminReport, fetchMe } from "../api.js";

const WINDOW_OPTIONS = [
  { hours: 1, label: "1 小時" },
  { hours: 24, label: "24 小時" },
  { hours: 168, label: "7 天" },
];

const RISK_COLORS = {
  low: "#2e7d32",
  medium: "#f9a825",
  high: "#c62828",
  critical: "#6a1b9a",
  unknown: "#9e9e9e",
};

function StatCard({ label, value, hint }) {
  return (
    <div className="report-stat-card">
      <div className="report-stat-label">{label}</div>
      <div className="report-stat-value">{value}</div>
      {hint ? <div className="report-stat-hint">{hint}</div> : null}
    </div>
  );
}

function formatBucketLabel(isoString, windowHours) {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  if (windowHours <= 1) {
    return date.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
  }
  if (windowHours <= 24) {
    return date.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("zh-TW", { month: "numeric", day: "numeric" });
}

function buildTimelineSeries(timeline, windowHours) {
  return (timeline || []).map((point) => ({
    ...point,
    label: formatBucketLabel(point.bucket_start, windowHours),
  }));
}

function buildRiskSeries(byRiskLevel) {
  return Object.entries(byRiskLevel || {}).map(([level, count]) => ({
    name: level,
    value: count,
    fill: RISK_COLORS[level] || RISK_COLORS.unknown,
  }));
}

export default function AdminEventsPage() {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [report, setReport] = useState(null);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [windowHours, setWindowHours] = useState(24);
  const [reportWindowHours, setReportWindowHours] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const requestIdRef = useRef(0);

  const refresh = useCallback(
    async (hours, isMounted = () => true) => {
      const requestId = ++requestIdRef.current;
      setRefreshing(true);
      try {
        const [eventsResult, reportResult] = await Promise.all([
          fetchAdminEvents(),
          fetchAdminReport(hours),
        ]);
        if (!isMounted() || requestId !== requestIdRef.current) {
          return;
        }

        const authFailure =
          (!eventsResult.ok && (eventsResult.status === 401 || eventsResult.status === 403)) ||
          (!reportResult.ok && (reportResult.status === 401 || reportResult.status === 403));
        if (authFailure) {
          navigate("/", { replace: true });
          return;
        }

        if (!eventsResult.ok) {
          setError(`事件請求失敗 (${eventsResult.status})`);
          return;
        }

        if (!reportResult.ok) {
          setReport(null);
          setReportWindowHours(null);
          setError(`報表請求失敗 (${reportResult.status})`);
          return;
        }

        setError("");
        setEvents(eventsResult.events);
        setReport(reportResult.body);
        setReportWindowHours(hours);
      } finally {
        if (isMounted() && requestId === requestIdRef.current) {
          setRefreshing(false);
        }
      }
    },
    [navigate],
  );

  useEffect(() => {
    let active = true;
    const isMounted = () => active;

    async function start() {
      const me = await fetchMe();
      if (!isMounted()) return;
      if (!me.ok || me.body?.role !== "admin") {
        navigate("/", { replace: true });
        return;
      }
      setProfile(me.body);
      await refresh(24, isMounted);
    }

    start();

    return () => {
      active = false;
    };
  }, [navigate, refresh]);

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
  const displayWindowHours = reportWindowHours ?? windowHours;
  const timelineSeries = buildTimelineSeries(login?.timeline, displayWindowHours);
  const riskSeries = buildRiskSeries(login?.by_risk_level);
  const windowLabel =
    WINDOW_OPTIONS.find((option) => option.hours === displayWindowHours)?.label ||
    `${displayWindowHours} 小時`;
  const windowPending = reportWindowHours !== null && windowHours !== reportWindowHours;

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
            安全數據儀表板。選擇時間範圍後按「刷新資料」更新 KPI、圖表與事件列表。
          </p>
        </div>
        <div className="dashboard-toolbar">
          <div className="dashboard-window-select">
            {WINDOW_OPTIONS.map((option) => (
              <button
                key={option.hours}
                type="button"
                className={
                  option.hours === windowHours
                    ? "dashboard-window-btn active"
                    : "dashboard-window-btn"
                }
                onClick={() => setWindowHours(option.hours)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="forgot-submit-btn dashboard-refresh-btn"
            onClick={() => refresh(windowHours, () => true)}
            disabled={refreshing}
          >
            {refreshing ? "刷新中…" : "刷新資料"}
          </button>
          <button
            type="button"
            className="forgot-submit-btn report-download-btn"
            onClick={downloadReport}
            disabled={!report}
          >
            下載 JSON 報表
          </button>
        </div>
      </div>
      {windowPending && (
        <p className="dashboard-pending-hint">已選擇新時間範圍，請按「刷新資料」載入。</p>
      )}
      {error && <p className="status error">{error}</p>}

      {report && (
        <section className="dashboard-section">
          <h2 className="dashboard-section-title">安全數據摘要（{windowLabel}）</h2>
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

          <div className="dashboard-chart-grid">
            <div className="dashboard-chart-panel">
              <h3 className="dashboard-chart-title">登入嘗試趨勢</h3>
              {timelineSeries.length === 0 || login?.total === 0 ? (
                <p className="dashboard-chart-empty">此時間範圍內沒有登入嘗試資料</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={timelineSeries} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e7ecf1" />
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} interval="preserveStartEnd" />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={36} />
                    <Tooltip
                      formatter={(value, name) => [value, name === "total" ? "總次數" : "成功"]}
                      labelFormatter={(label) => `時間：${label}`}
                    />
                    <Legend formatter={(value) => (value === "total" ? "總次數" : "成功")} />
                    <Line
                      type="monotone"
                      dataKey="total"
                      stroke="#0033a0"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="successes"
                      stroke="#2e7d32"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="dashboard-chart-panel">
              <h3 className="dashboard-chart-title">風險等級分布</h3>
              {riskSeries.length === 0 ? (
                <p className="dashboard-chart-empty">此時間範圍內沒有風險等級資料</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={riskSeries}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={56}
                      outerRadius={96}
                      paddingAngle={2}
                      label={({ name, percent }) =>
                        `${name} ${(percent * 100).toFixed(0)}%`
                      }
                    >
                      {riskSeries.map((entry) => (
                        <Cell key={entry.name} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value, name) => [value, `風險：${name}`]} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </section>
      )}

      <div className="dashboard-panel">
        <h2 className="dashboard-section-title">即時稽核事件</h2>
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
