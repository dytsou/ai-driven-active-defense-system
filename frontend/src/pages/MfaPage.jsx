import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import PortalLayout from "../components/PortalLayout.jsx";
import { PortalIconSprite } from "../components/PortalIcons.jsx";
import { fetchMe, mfaSend, mfaVerify } from "../api.js";

function BackArrowIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="16" height="16" aria-hidden="true">
      <path d="M14 26L4 16 14 6l1.41 1.41L7.83 15H28v2H7.83l7.58 7.59L14 26z" />
    </svg>
  );
}

function MfaPanelShell({ children }) {
  return (
    <PortalLayout>
      <PortalIconSprite />
      <div className="auth-panels">
        <div
          className="auth-panel auth-panel--forgot is-active"
          role="region"
          aria-labelledby="mfa-title"
          aria-hidden="false"
        >
          {children}
        </div>
      </div>
    </PortalLayout>
  );
}

export default function MfaPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const challengeId = searchParams.get("challenge_id") || "";
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  if (!challengeId) {
    return (
      <MfaPanelShell>
        <div className="modern-login-form forgot-flow-form">
          <div className="forgot-form-header">
            <div className="forgot-header-top">
              <Link to="/" className="forgot-back-btn">
                <BackArrowIcon />
                <span>回登入頁</span>
              </Link>
            </div>
            <h2 className="forgot-page-title" id="mfa-title">
              <span className="forgot-title-accent">OTP 驗證/</span>
              <span className="forgot-title-rest">電子郵件</span>
            </h2>
          </div>
          <div className="forgot-form-content">
            <p className="welcome-title-description" style={{ minHeight: "auto", margin: 0 }}>
              缺少驗證資訊，請重新登入。
            </p>
            <Link to="/" className="link-forgot">
              返回登入頁
            </Link>
          </div>
        </div>
      </MfaPanelShell>
    );
  }

  async function runOnce(fn) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await fn();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function handleSend() {
    await runOnce(async () => {
      setStatus("寄送中...");
      const { body } = await mfaSend(challengeId);
      setOtpSent(true);
      setStatus(body.message || "驗證碼已寄出，請至 Mailhog 查看");
    });
  }

  async function handleVerify(event) {
    event.preventDefault();
    await runOnce(async () => {
      setStatus("驗證中...");
      const { body } = await mfaVerify(challengeId, otp);
      if (body.status === "success") {
        const me = await fetchMe();
        if (me.ok && me.body?.role === "admin") {
          navigate("/admin/events");
          return;
        }
        navigate("/me");
        return;
      }
      setStatus(body.message || body.status);
    });
  }

  const progressWidth = otp.length === 6 ? "100%" : otpSent ? "66%" : "33%";

  return (
    <MfaPanelShell>
      <form className="modern-login-form forgot-flow-form" onSubmit={handleVerify} autoComplete="off">
        <div className="forgot-form-header">
          <div className="forgot-header-top">
            <Link to="/" className="forgot-back-btn">
              <BackArrowIcon />
              <span>回登入頁</span>
            </Link>
          </div>
          <h2 className="forgot-page-title" id="mfa-title">
            <span className="forgot-title-accent">OTP 驗證/</span>
            <span className="forgot-title-rest">電子郵件</span>
          </h2>
        </div>

        <div className="forgot-step-indicator">
          <div className="forgot-steps">
            <div className="forgot-step active">
              <div className="forgot-step-number">1</div>
              <div className="forgot-step-title">帳號驗證</div>
            </div>
            <div className={`forgot-step${otpSent ? " active" : " disabled"}`}>
              <div className="forgot-step-number">2</div>
              <div className="forgot-step-title">OTP 驗證</div>
            </div>
            <div className="forgot-step disabled">
              <div className="forgot-step-number">3</div>
              <div className="forgot-step-title">完成登入</div>
            </div>
          </div>
          <div className="forgot-step-progress-wrap">
            <div className="forgot-step-progress" style={{ width: progressWidth }} />
          </div>
        </div>

        <div className="forgot-form-content">
          <p className="welcome-title-description mfa-flow-hint">
            為保障帳號安全，請完成電子郵件 OTP 雙重驗證。驗證碼將寄送至您註冊的電子信箱。
          </p>

          <div className="forgot-field-group">
            <label htmlFor="otp">驗證碼</label>
            <div className="forgot-input-suffix-wrap">
              <input
                className="forgot-input-inner"
                type="text"
                id="otp"
                name="otp"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                maxLength={6}
                placeholder="000000"
                inputMode="numeric"
                autoComplete="one-time-code"
                disabled={busy}
              />
              <span className="forgot-input-suffix" aria-hidden="true">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
                  <path d="M28 6H4a2 2 0 00-2 2v16a2 2 0 002 2h24a2 2 0 002-2V8a2 2 0 00-2-2zm0 18H4V8h24zM8 12h2v2H8zm4 0h12v2H12zm-4 6h2v2H8zm4 0h8v2h-8z" />
                </svg>
              </span>
            </div>
          </div>

          <button
            type="button"
            className="forgot-submit-btn mfa-action-btn"
            onClick={handleSend}
            disabled={busy}
          >
            寄送驗證碼
          </button>
          <button
            type="submit"
            className="forgot-submit-btn"
            disabled={busy || otp.length !== 6}
          >
            確認驗證
          </button>

          {status && (
            <p className={`status${status.includes("失敗") || status.includes("錯誤") ? " error" : ""}`}>
              {status}
            </p>
          )}
        </div>
      </form>
    </MfaPanelShell>
  );
}
