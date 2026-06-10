import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import PortalLayout from "../components/PortalLayout.jsx";
import PortalForgotPanel from "../components/PortalForgotPanel.jsx";
import PortalHelpModal from "../components/PortalHelpModal.jsx";
import { PortalIconSprite } from "../components/PortalIcons.jsx";
import { fetchMe, login } from "../api.js";
import { useKeystroke } from "../hooks/useKeystroke.js";
import { usePortalPanels } from "../hooks/usePortalPanels.js";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const oauthError = searchParams.get("oauth_error");
  const { keyHandlers, getPayload } = useKeystroke();
  const { activePanel, showPanel, panelClass, panelAriaHidden } = usePortalPanels();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setStatus("登入中...");
    try {
      const { body } = await login({
        username,
        password,
        keystroke: getPayload(),
      });
      if (body.status === "success") {
        const me = await fetchMe();
        if (me.ok && me.body?.role === "admin") {
          navigate("/admin/events");
          return;
        }
        navigate("/me");
        return;
      }
      if (body.status === "registration_required") {
        navigate("/register", {
          state: {
            registrationRequired: true,
            username: username.trim(),
            message: body.message || "請先完成 NYCU + LINE 註冊",
          },
        });
        return;
      }
      if (body.status === "mfa_required" && body.challenge_id) {
        navigate(`/mfa?challenge_id=${encodeURIComponent(body.challenge_id)}`, {
          state: {
            autoSent: Boolean(body.delivery_targets?.length),
            deliveryTargets: body.delivery_targets || [],
            debugOtp: body.debug_otp || null,
          },
        });
        return;
      }
      setStatus(body.message || body.status);
    } catch {
      setStatus("網路連線錯誤，請稍後再試");
    } finally {
      setLoading(false);
    }
  }

  function togglePassword() {
    setShowPassword((visible) => !visible);
  }

  return (
    <PortalLayout>
      <PortalIconSprite />
      <div className="auth-panels" id="auth-panels">
        <div
          className={panelClass("login")}
          id="panel-login"
          role="region"
          aria-labelledby="login-title"
          aria-hidden={panelAriaHidden("login")}
        >
          <form className="modern-login-form" onSubmit={handleSubmit} autoComplete="on">
            <div className="welcome-title-container">
              <div className="welcome-title" id="login-title">
                登入單一入口網站
              </div>
              <span className="welcome-title-description">
                第一次登入嗎？
                <button type="button" className="link-field" onClick={() => setHelpOpen(true)}>
                  點我查看帳號填寫說明
                </button>
              </span>
            </div>

            <div className="input-group">
              <div className="form-group">
                <label className="form-input-label-text" htmlFor="username">
                  帳號
                </label>
                <div className="form-input-wrapper">
                  <span className="form-input-icon" aria-hidden="true">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 130 130" fill="currentColor">
                      <use href="#portal-icon-user" />
                    </svg>
                  </span>
                  <input
                    className="form-input"
                    type="text"
                    id="username"
                    name="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    placeholder="請輸入您的帳號"
                    autoComplete="username"
                    inputMode="text"
                    {...keyHandlers}
                  />
                </div>
              </div>

              <div className="form-group has-toggle">
                <label className="form-input-label-text" htmlFor="password">
                  密碼
                </label>
                <div className="form-input-wrapper">
                  <span className="form-input-icon" aria-hidden="true">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" fill="currentColor">
                      <use href="#portal-icon-password" />
                    </svg>
                  </span>
                  <input
                    className="form-input"
                    type={showPassword ? "text" : "password"}
                    id="password"
                    name="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="請輸入您的密碼"
                    autoComplete="current-password"
                    {...keyHandlers}
                  />
                  <button
                    type="button"
                    className="form-input-toggle"
                    onClick={togglePassword}
                    aria-label={showPassword ? "隱藏密碼" : "顯示密碼"}
                    aria-pressed={showPassword}
                    title={showPassword ? "密碼顯示中（點擊隱藏）" : "顯示密碼"}
                    data-state={showPassword ? "visible" : "hidden"}
                  >
                    {!showPassword ? (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="pw-toggle-svg"
                        viewBox="0 0 128 64"
                        width="16"
                        height="16"
                        fill="currentColor"
                        aria-hidden="true"
                      >
                        <use href="#portal-icon-eye-off" />
                      </svg>
                    ) : (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="pw-toggle-svg"
                        viewBox="0 0 1024 1024"
                        width="16"
                        height="16"
                        fill="currentColor"
                        aria-hidden="true"
                      >
                        <use href="#portal-icon-eye-on" />
                      </svg>
                    )}
                  </button>
                </div>
                <button type="button" className="link-forgot" onClick={() => showPanel("forgot")}>
                  忘記密碼？
                </button>
              </div>
            </div>

            <div className="button-group">
              <button
                type="submit"
                className="carbon-button carbon-button--primary carbon-button--large carbon-button--full-width carbon-button--with-arrow"
                disabled={loading}
              >
                {loading ? "登入中..." : "帳號登入"}
                <div className="arrow-icon" aria-hidden="true">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16" fill="none">
                    <path
                      d="M6 12L10 8L6 4"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              </button>
              <button
                type="button"
                className="carbon-button carbon-button--ghost carbon-button--large carbon-button--full-width enable-account-button"
                onClick={() => navigate("/register")}
              >
                註冊帳號（NYCU + LINE）
              </button>
            </div>

            {(oauthError || status) && (
              <p
                className={`status${
                  oauthError || status.includes("錯誤") || status.includes("失敗") ? " error" : ""
                }`}
              >
                {oauthError ? `OAuth 登入失敗：${oauthError}` : status}
              </p>
            )}
          </form>
        </div>

        <PortalForgotPanel
          isActive={activePanel === "forgot"}
          onBack={() => showPanel("login")}
          onOpenHelp={() => setHelpOpen(true)}
        />
      </div>

      <PortalHelpModal isOpen={helpOpen} onClose={() => setHelpOpen(false)} />
    </PortalLayout>
  );
}
