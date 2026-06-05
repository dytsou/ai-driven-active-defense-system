import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout.jsx";
import { fetchMe } from "../api.js";

const PORTAL_SYSTEM_LINKS = [
  "SciVal 研究平台 [不提供直接登入]",
  "兼任差勤(受雇者線上簽到退)",
  "人力資源系統",
  "資訊中心服務追蹤系統",
  "E3數位教學平台",
];

function formatCreatedAt(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-TW");
}

function roleLabel(role) {
  if (role === "admin") return "管理員";
  return "一般使用者";
}

export default function MePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [status, setStatus] = useState("載入中...");

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
        setStatus(`請求失敗 (${me.status})`);
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
    <DashboardLayout
      username={profile?.username}
      role={profile?.role}
      isAdmin={profile?.role === "admin"}
      breadcrumb="陽明交通大學"
    >
      {status && <p className="status">{status}</p>}

      {profile && (
        <>
          <div className="dashboard-banner">
            <strong>登入成功！</strong> 您已通過主動式防禦登入驗證。
          </div>

          <section className="dashboard-section">
            <h2 className="dashboard-section-title">校務系統連結</h2>
            <ul className="dashboard-system-list">
              {PORTAL_SYSTEM_LINKS.map((label) => (
                <li key={label}>
                  <span>{label}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="dashboard-section">
            <h2 className="dashboard-section-title">個人資料</h2>
            <p className="dashboard-subtitle">以下為您的帳號資訊。</p>
            <div className="dashboard-panel profile-card">
              <dl>
                <dt>使用者 ID</dt>
                <dd>{profile.id}</dd>

                <dt>帳號</dt>
                <dd>{profile.username}</dd>

                <dt>電子郵件</dt>
                <dd>{profile.email}</dd>

                <dt>角色</dt>
                <dd>{roleLabel(profile.role)}</dd>

                <dt>MFA 方式</dt>
                <dd>{profile.mfa_method}</dd>

                <dt>帳號狀態</dt>
                <dd>{profile.is_active ? "啟用中" : "已停用"}</dd>

                <dt>建立時間</dt>
                <dd>{formatCreatedAt(profile.created_at)}</dd>
              </dl>
            </div>
          </section>
        </>
      )}
    </DashboardLayout>
  );
}
