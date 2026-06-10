import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout.jsx";
import { fetchMe, updateMfaPreferences } from "../api.js";

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

function mfaMethodLabel(value) {
  if (value === "both") return "Email + LINE";
  if (value === "line") return "LINE";
  return "Email";
}

export default function MePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [status, setStatus] = useState("載入中...");
  const [savingMfa, setSavingMfa] = useState(false);

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

  async function handleMfaLineToggle(enabled) {
    if (!profile) return;
    setSavingMfa(true);
    setStatus("");
    try {
      const result = await updateMfaPreferences({ mfaLineEnabled: enabled });
      if (!result.ok) {
        setStatus(result.body?.detail || `更新失敗 (${result.status})`);
        return;
      }
      setProfile((current) => ({
        ...current,
        mfa_line_enabled: result.body.mfa_line_enabled,
        mfa_method: result.body.mfa_method,
        mfa_channels: result.body.mfa_channels,
      }));
      setStatus("MFA 設定已更新");
    } finally {
      setSavingMfa(false);
    }
  }

  return (
    <DashboardLayout
      username={profile?.username}
      role={profile?.role}
      isAdmin={profile?.role === "admin"}
      breadcrumb="陽明交通大學"
    >
      {status && <p className="status">{status}</p>}

      {profile && (
        <section className="dashboard-section">
          <h2 className="dashboard-section-title">個人資料</h2>
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
              <dd>{mfaMethodLabel(profile.mfa_method)}</dd>

              {profile.line_mfa_available && (
                <>
                  <dt>LINE MFA</dt>
                  <dd>
                    <label className="profile-mfa-toggle">
                      <input
                        type="checkbox"
                        checked={Boolean(profile.mfa_line_enabled)}
                        disabled={savingMfa}
                        onChange={(e) => handleMfaLineToggle(e.target.checked)}
                      />
                      透過 LINE 接收驗證碼
                    </label>
                    <p className="profile-mfa-hint">
                      Email 驗證碼預設一律啟用；可在此關閉 LINE 推播。
                    </p>
                  </dd>
                </>
              )}

              <dt>帳號狀態</dt>
              <dd>{profile.is_active ? "啟用中" : "已停用"}</dd>

              <dt>建立時間</dt>
              <dd>{formatCreatedAt(profile.created_at)}</dd>
            </dl>
          </div>
        </section>
      )}
    </DashboardLayout>
  );
}
