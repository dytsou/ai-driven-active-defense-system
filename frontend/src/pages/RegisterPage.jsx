import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import PortalLayout from "../components/PortalLayout.jsx";
import { PortalIconSprite } from "../components/PortalIcons.jsx";
import {
  registerComplete,
  registerLineStart,
  registerStart,
  registerStatus,
} from "../api.js";

const ERROR_MESSAGES = {
  identity_already_bound: "此 NYCU 或 LINE 帳號已綁定其他使用者",
  identity_conflict: "此帳號與註冊流程不符，請重新開始",
  line_already_bound: "此 LINE 帳號已被使用",
  invalid_registration_token: "註冊逾時，請重新開始",
  invalid_state: "OAuth 狀態無效，請重新開始",
};

export default function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const tokenParam = searchParams.get("token") || "";
  const stepParam = searchParams.get("step") || "";
  const errorParam = searchParams.get("error") || "";

  const [token, setToken] = useState(tokenParam);
  const [step, setStep] = useState(stepParam || "start");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [lineFriendConfirmed, setLineFriendConfirmed] = useState(false);
  const [lineOfficialAccountUrl, setLineOfficialAccountUrl] = useState("");

  useEffect(() => {
    if (tokenParam) setToken(tokenParam);
    if (stepParam) setStep(stepParam);
    if (errorParam) {
      setStatus(ERROR_MESSAGES[errorParam] || errorParam);
    }
  }, [tokenParam, stepParam, errorParam]);

  useEffect(() => {
    if (!token) return;
    registerStatus(token).then(({ body }) => {
      if (body.step) setStep(body.step);
      if (body.line_official_account_url) {
        setLineOfficialAccountUrl(body.line_official_account_url);
      }
    });
  }, [token]);

  async function handleStart() {
    setLoading(true);
    setStatus("");
    try {
      const { body } = await registerStart();
      if (body.status === "started" && body.nycu_authorization_url) {
        window.location.href = body.nycu_authorization_url;
        return;
      }
      setStatus(body.message || "無法開始註冊");
    } finally {
      setLoading(false);
    }
  }

  async function handleLineStart() {
    if (!token) return;
    setLoading(true);
    try {
      const { body } = await registerLineStart(token);
      if (body.line_authorization_url) {
        window.location.href = body.line_authorization_url;
        return;
      }
      setStatus(body.message || body.status);
    } finally {
      setLoading(false);
    }
  }

  async function handleComplete() {
    if (!token || !lineFriendConfirmed) return;
    setLoading(true);
    try {
      const { body } = await registerComplete(token);
      if (body.status === "complete") {
        setStep("done");
        setStatus("註冊完成，請返回登入");
        if (body.line_official_account_url) {
          setLineOfficialAccountUrl(body.line_official_account_url);
        }
        return;
      }
      setStatus(body.message || body.status);
    } finally {
      setLoading(false);
    }
  }

  return (
    <PortalLayout>
      <PortalIconSprite />
      <div className="auth-panels">
        <div className="auth-panel auth-panel--activate is-active">
          <div className="activate-flow-layout">
            <h2 className="activate-page-title">首次使用 · 完成註冊</h2>
            <p className="welcome-title-description">
              請依序完成 NYCU 帳號驗證、LINE 綁定，並加入官方 LINE 帳號以接收 MFA 驗證碼。
            </p>

            {step === "start" && (
              <button type="button" className="forgot-submit-btn" onClick={handleStart} disabled={loading}>
                以 NYCU 帳號開始
              </button>
            )}

            {(step === "line" || step === "pending_line") && (
              <>
                <p>NYCU 已驗證，請綁定 LINE</p>
                <button type="button" className="forgot-submit-btn" onClick={handleLineStart} disabled={loading}>
                  綁定 LINE
                </button>
              </>
            )}

            {(step === "friend" || step === "pending_friend") && (
              <>
                <p>請加入 LINE 官方帳號為好友，以便接收 MFA 驗證碼。</p>
                {lineOfficialAccountUrl ? (
                  <a
                    href={lineOfficialAccountUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="forgot-submit-btn register-line-friend-link"
                  >
                    加入官方 LINE 帳號
                  </a>
                ) : (
                  <p className="status">
                    尚未設定官方 LINE 加好友連結（請在伺服器設定 LINE_OFFICIAL_ACCOUNT_URL）。
                  </p>
                )}
                {lineOfficialAccountUrl && (
                  <p className="register-line-friend-url">
                    <a
                      href={lineOfficialAccountUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="activate-link"
                    >
                      {lineOfficialAccountUrl}
                    </a>
                  </p>
                )}
                <label>
                  <input
                    type="checkbox"
                    checked={lineFriendConfirmed}
                    onChange={(e) => setLineFriendConfirmed(e.target.checked)}
                  />
                  我已加入官方 LINE 帳號
                </label>
                <button
                  type="button"
                  className="forgot-submit-btn"
                  onClick={handleComplete}
                  disabled={loading || !lineFriendConfirmed}
                >
                  完成註冊
                </button>
              </>
            )}

            {step === "done" && (
              <>
                {lineOfficialAccountUrl && (
                  <div className="register-line-friend-done">
                    <p>若尚未加入官方 LINE，請點下方連結加好友以接收 MFA 驗證碼：</p>
                    <a
                      href={lineOfficialAccountUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="forgot-submit-btn register-line-friend-link"
                    >
                      加入官方 LINE 帳號
                    </a>
                    <p className="register-line-friend-url">
                      <a
                        href={lineOfficialAccountUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="activate-link"
                      >
                        {lineOfficialAccountUrl}
                      </a>
                    </p>
                  </div>
                )}
                <button type="button" className="forgot-submit-btn" onClick={() => navigate("/")}>
                  返回登入
                </button>
              </>
            )}

            {status && <p className="status">{status}</p>}
            <Link to="/" className="link-forgot">
              返回登入頁
            </Link>
          </div>
        </div>
      </div>
    </PortalLayout>
  );
}
