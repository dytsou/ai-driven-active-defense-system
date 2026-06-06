import { useState } from "react";
import { usePortalFlowI18n } from "../hooks/usePortalFlowI18n.js";

const DEMO_MESSAGE = "此為示範頁面，請返回登入頁使用帳號登入。";

function BackArrowIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="16" height="16" aria-hidden="true">
      <path d="M14 26L4 16 14 6l1.41 1.41L7.83 15H28v2H7.83l7.58 7.59L14 26z" />
    </svg>
  );
}

function LangSwitcher({ locale, setFlowLocale, classPrefix }) {
  return (
    <div className={`${classPrefix}-lang-switcher`} role="group" aria-label="語言">
      <button
        type="button"
        className={`${classPrefix}-lang-btn${locale === "zh" ? " active" : ""}`}
        aria-pressed={locale === "zh"}
        onClick={() => setFlowLocale("zh")}
      >
        中文
      </button>
      <button
        type="button"
        className={`${classPrefix}-lang-btn${locale === "en" ? " active" : ""}`}
        aria-pressed={locale === "en"}
        onClick={() => setFlowLocale("en")}
      >
        English
      </button>
    </div>
  );
}

export default function PortalForgotPanel({ isActive, onBack, onOpenHelp }) {
  const { locale, t, setFlowLocale } = usePortalFlowI18n();
  const [account, setAccount] = useState("");
  const [message, setMessage] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    if (!account.trim()) return;
    setMessage(DEMO_MESSAGE);
  }

  return (
    <div
      className={`auth-panel auth-panel--forgot${isActive ? " is-active" : ""}`}
      id="panel-forgot"
      role="region"
      aria-labelledby="forgot-title"
      aria-hidden={!isActive}
    >
      <form className="modern-login-form forgot-flow-form" onSubmit={handleSubmit} autoComplete="on">
        <div className="forgot-form-header">
          <div className="forgot-header-top">
            <button type="button" className="forgot-back-btn" onClick={onBack}>
              <BackArrowIcon />
              <span>{t("forgot.backButton")}</span>
            </button>
            <LangSwitcher locale={locale} setFlowLocale={setFlowLocale} classPrefix="forgot" />
          </div>
          <h2 className="forgot-page-title" id="forgot-title">
            <span className="forgot-title-accent">{t("forgot.titleAccent")}</span>
            <span className="forgot-title-rest">{t("forgot.titleRest")}</span>
          </h2>
        </div>

        <div className="forgot-step-indicator">
          <div className="forgot-steps">
            <div className="forgot-step active">
              <div className="forgot-step-number">1</div>
              <div className="forgot-step-title">{t("forgot.step1")}</div>
            </div>
            <div className="forgot-step disabled">
              <div className="forgot-step-number">2</div>
              <div className="forgot-step-title">{t("forgot.step2")}</div>
            </div>
            <div className="forgot-step disabled">
              <div className="forgot-step-number">3</div>
              <div className="forgot-step-title">{t("forgot.step3")}</div>
            </div>
          </div>
          <div className="forgot-step-progress-wrap">
            <div className="forgot-step-progress" style={{ width: "0%" }} />
          </div>
        </div>

        <div className="forgot-form-content">
          <div className="forgot-field-group">
            <label htmlFor="forgot-account">{t("forgot.labelAccount")}</label>
            <div className="forgot-input-container">
              <div className="forgot-input-suffix-wrap">
                <input
                  className="forgot-input-inner"
                  type="text"
                  name="account"
                  id="forgot-account"
                  value={account}
                  onChange={(e) => setAccount(e.target.value)}
                  placeholder={t("forgot.placeholderAccount")}
                  autoComplete="username"
                  inputMode="text"
                />
                <span className="forgot-input-suffix" aria-hidden="true">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 130 130" fill="currentColor">
                    <use href="#portal-icon-user" />
                  </svg>
                </span>
              </div>
              <button
                type="button"
                className="forgot-info-icon"
                title={t("forgot.infoTitle")}
                aria-label={t("forgot.infoTitle")}
                onClick={onOpenHelp}
              >
                ?
              </button>
            </div>
          </div>
          <button type="submit" className="forgot-submit-btn" disabled={!account.trim()}>
            {t("forgot.submit")}
          </button>
          {message && <p className="status">{message}</p>}
        </div>
      </form>
    </div>
  );
}
