import { useEffect, useRef } from "react";
import { usePortalFlowI18n } from "../hooks/usePortalFlowI18n.js";

export default function PortalHelpModal({ isOpen, onClose }) {
  const { t } = usePortalFlowI18n();
  const closeRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    closeRef.current?.focus();
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="help-overlay is-open"
      aria-hidden="false"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="help-overlay__surface"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-dialog-title"
        tabIndex={-1}
      >
        <div className="help-dialog-inner">
          <h2 id="help-dialog-title">{t("help.title")}</h2>
          <div className="dialog-section-title">{t("help.sectionZh")}</div>
          <ul className="dialog-list">
            <li>
              <span className="dialog-label">學生：</span>請輸入
              <span className="dialog-highlight">學號</span>
            </li>
            <li>
              <span className="dialog-label">教職員：</span>請輸入
              <span className="dialog-highlight">人事代號</span>
            </li>
            <li>
              <span className="dialog-label">校友及其他：</span>請輸入
              <span className="dialog-highlight">Email</span>
            </li>
          </ul>
          <div className="dialog-section-title">{t("help.sectionEn")}</div>
          <ul className="dialog-list">
            <li>
              <span className="dialog-label">Students:</span> use your{" "}
              <span className="dialog-highlight">Student ID</span>
            </li>
            <li>
              <span className="dialog-label">Faculty/Staff:</span> use your{" "}
              <span className="dialog-highlight">Faculty/Staff ID</span>
            </li>
            <li>
              <span className="dialog-label">Alumni and Others:</span> use your{" "}
              <span className="dialog-highlight">Email</span>
            </li>
          </ul>
          <button type="button" className="help-close" ref={closeRef} onClick={onClose}>
            {t("help.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
