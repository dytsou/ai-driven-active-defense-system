import { useState } from "react";
import { usePortalFlowI18n } from "../hooks/usePortalFlowI18n.js";

const DEMO_MESSAGE = "此為示範頁面，請返回登入頁使用帳號登入。";
const ACTIVATE_GUIDE_URL =
  "https://it.nycu.edu.tw/it/ch/app/artwebsite/view?module=artwebsite&id=27&serno=97742641-5a31-4c95-a4f5-f9a737cf7984";

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

export default function PortalActivatePanel({ isActive, onBack }) {
  const { locale, t, setFlowLocale } = usePortalFlowI18n();
  const [showingForm, setShowingForm] = useState(false);
  const [identity, setIdentity] = useState("");
  const [account, setAccount] = useState("");
  const [birthday, setBirthday] = useState("");
  const [personalId, setPersonalId] = useState("");
  const [message, setMessage] = useState("");

  const backLabel = showingForm ? t("activate.backLoginShort") : t("activate.backLoginPage");
  const titleRest = showingForm ? t("activate.titleConfirm") : t("activate.titleSelect");
  const canSubmit = account.trim() && birthday.trim() && personalId.trim();

  function handleBack() {
    resetForm();
    setShowingForm(false);
    onBack();
  }

  function resetForm() {
    setIdentity("");
    setAccount("");
    setBirthday("");
    setPersonalId("");
    setMessage("");
  }

  function selectIdentity(id) {
    setIdentity(id);
    setShowingForm(true);
    setMessage("");
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    setMessage(DEMO_MESSAGE);
  }

  return (
    <div
      className={`auth-panel auth-panel--activate${isActive ? " is-active" : ""}`}
      id="panel-activate"
      role="region"
      aria-labelledby="activate-main-title"
      aria-hidden={!isActive}
    >
      <div className="activate-flow-layout">
        <div className="activate-shared-header">
          <div className="activate-header-top">
            <button type="button" className="activate-back-btn" onClick={handleBack}>
              <BackArrowIcon />
              <span>{backLabel}</span>
            </button>
            <LangSwitcher locale={locale} setFlowLocale={setFlowLocale} classPrefix="activate" />
          </div>
          <h2 className="activate-page-title" id="activate-main-title">
            <span className="activate-title-accent">{t("activate.titleAccent")}</span>
            <span className="activate-title-rest">{titleRest}</span>
          </h2>
        </div>

        {!showingForm ? (
          <div id="activate-body-selector" className="activate-selector-body">
            <div className="activate-info">
              <span>{t("activate.infoBefore")}</span>
              <a
                href={ACTIVATE_GUIDE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="activate-link"
              >
                {t("activate.infoLink")}
              </a>
            </div>
            <button
              type="button"
              className="identity-select-box"
              data-identity="staff-student"
              onClick={() => selectIdentity("staff-student")}
            >
              <div className="identity-select-box-icon" aria-hidden="true">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="identity-icon-key"
                >
                  <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
                </svg>
              </div>
              <div className="identity-select-box-content">
                <div className="identity-select-box-name">{t("activate.card1Name")}</div>
                <div className="identity-select-box-description">{t("activate.card1Desc")}</div>
              </div>
            </button>
            <button
              type="button"
              className="identity-select-box"
              data-identity="alumni"
              onClick={() => selectIdentity("alumni")}
            >
              <div className="identity-select-box-icon" aria-hidden="true">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
                  <path d="M28,6H4A2,2,0,0,0,2,8V24a2,2,0,0,0,2,2H28a2,2,0,0,0,2-2V8A2,2,0,0,0,28,6ZM25.8,8,16,14.7,6.2,8ZM4,24V9.9l12,8,12-8V24Z" />
                </svg>
              </div>
              <div className="identity-select-box-content">
                <div className="identity-select-box-name">{t("activate.card2Name")}</div>
                <div className="identity-select-box-description">{t("activate.card2Desc")}</div>
              </div>
            </button>
          </div>
        ) : (
          <form
            id="activate-body-form"
            className="activate-form-step forgot-flow-form"
            onSubmit={handleSubmit}
            autoComplete="on"
          >
            <input type="hidden" name="identity" value={identity} />
            <div className="forgot-step-indicator">
              <div className="forgot-steps">
                <div className="forgot-step active">
                  <div className="forgot-step-number">1</div>
                  <div className="forgot-step-title">{t("activate.stepConfirm")}</div>
                </div>
                <div className="forgot-step disabled">
                  <div className="forgot-step-number">2</div>
                  <div className="forgot-step-title">{t("activate.stepMailbox")}</div>
                </div>
                <div className="forgot-step disabled">
                  <div className="forgot-step-number">3</div>
                  <div className="forgot-step-title">{t("activate.stepPassword")}</div>
                </div>
              </div>
              <div className="forgot-step-progress-wrap">
                <div className="forgot-step-progress" style={{ width: "0%" }} />
              </div>
            </div>

            <div className="forgot-form-content">
              <div className="forgot-field-group">
                <label htmlFor="activate-account">{t("activate.labelAccount")}</label>
                <div className="forgot-input-suffix-wrap">
                  <input
                    className="forgot-input-inner"
                    type="text"
                    name="account"
                    id="activate-account"
                    value={account}
                    onChange={(e) => setAccount(e.target.value)}
                    placeholder={t("activate.phAccount")}
                    autoComplete="username"
                    inputMode="text"
                  />
                  <span className="forgot-input-suffix" aria-hidden="true">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 130 130" fill="currentColor">
                      <use href="#portal-icon-user" />
                    </svg>
                  </span>
                </div>
              </div>
              <div className="forgot-field-group">
                <label htmlFor="activate-birthday">{t("activate.labelBirth")}</label>
                <div className="activate-date-editor">
                  <span className="activate-input-prefix" aria-hidden="true">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
                      <path d="M26 4H22V2H20V4H12V2H10V4H6A2 2 0 004 6V26a2 2 0 002 2H26a2 2 0 002-2V6a2 2 0 00-2-2zm0 22H6V12H26zM6 10V6h4v2h2V6h8v2h2V6h4v4z" />
                    </svg>
                  </span>
                  <input
                    className="forgot-input-inner activate-input-with-prefix"
                    type="date"
                    name="birthday"
                    id="activate-birthday"
                    value={birthday}
                    onChange={(e) => setBirthday(e.target.value)}
                  />
                </div>
              </div>
              <div className="forgot-field-group">
                <label htmlFor="activate-personal-id">{t("activate.labelId")}</label>
                <div className="forgot-input-suffix-wrap">
                  <input
                    className="forgot-input-inner"
                    type="text"
                    name="personalId"
                    id="activate-personal-id"
                    value={personalId}
                    onChange={(e) => setPersonalId(e.target.value)}
                    placeholder={t("activate.phId")}
                    autoComplete="off"
                    inputMode="text"
                  />
                  <span className="forgot-input-suffix" aria-hidden="true">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
                      <path d="M28 6H4a2 2 0 00-2 2v16a2 2 0 002 2h24a2 2 0 002-2V8a2 2 0 00-2-2zm0 18H4V8h24zM8 12h2v2H8zm4 0h12v2H12zm-4 6h2v2H8zm4 0h8v2h-8z" />
                    </svg>
                  </span>
                </div>
              </div>
            </div>
            <button type="submit" className="forgot-submit-btn" disabled={!canSubmit}>
              {t("activate.submit")}
            </button>
            {message && <p className="status">{message}</p>}
          </form>
        )}
      </div>
    </div>
  );
}
