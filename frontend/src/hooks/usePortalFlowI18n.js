import { useState } from "react";

export const FLOW_I18N = {
  zh: {
    "forgot.backButton": "回登入頁",
    "forgot.titleAccent": "忘記密碼/",
    "forgot.titleRest": "確認身分",
    "forgot.step1": "確認身份",
    "forgot.step2": "OTP 驗證",
    "forgot.step3": "重設密碼",
    "forgot.labelAccount": "帳號",
    "forgot.placeholderAccount": "帳號",
    "forgot.infoTitle": "帳號填寫說明",
    "forgot.submit": "確認身分",
    "activate.backLoginPage": "返回登入頁面",
    "activate.backLoginShort": "回登入頁",
    "activate.titleAccent": "啟用帳號/",
    "activate.titleSelect": "請選擇您的身份",
    "activate.titleConfirm": "確認身分",
    "activate.infoBefore": "首次使用 NYCU Portal？請先閱讀",
    "activate.infoLink": "啟用說明",
    "activate.card1Name": "教職員/學生/兼任助理",
    "activate.card1Desc": "在學學士/碩/博士/產學專班/教職員/工讀生",
    "activate.card2Name": "校友",
    "activate.card2Desc": "已通過審核之畢業校友",
    "activate.stepConfirm": "確認身分",
    "activate.stepMailbox": "申請信箱",
    "activate.stepPassword": "設定密碼",
    "activate.labelAccount": "帳號",
    "activate.phAccount": "請輸入帳號 (學號/人事代號)",
    "activate.labelBirth": "西元生日",
    "activate.labelId": "身分證／居留證號",
    "activate.phId": "請輸入身分證或居留證號碼",
    "activate.submit": "確認身分",
    "help.title": "帳號填寫說明",
    "help.sectionDemo": "系統試用帳號",
    "help.demoAdmin": "管理員（威脅監控後台）",
    "help.demoUser": "一般使用者（demo1 含 keystroke baseline）",
    "help.demoNote": "試用帳號使用本機密碼登入，不需 NYCU 註冊；MFA 驗證碼請至 Mailhog 查看。",
    "help.sectionZh": "NYCU 正式帳號（中文）",
    "help.sectionEn": "NYCU accounts (English)",
    "help.close": "關閉",
    "login.trialHint": "試用帳號：",
    "login.trialAccounts": "admin、demo1、demo2",
    "login.trialHelp": "查看密碼與說明",
  },
  en: {
    "forgot.backButton": "Back to login",
    "forgot.titleAccent": "Forgot password/",
    "forgot.titleRest": "Confirm identity",
    "forgot.step1": "Verify identity",
    "forgot.step2": "OTP verification",
    "forgot.step3": "Reset password",
    "forgot.labelAccount": "Account",
    "forgot.placeholderAccount": "Account",
    "forgot.infoTitle": "Account help",
    "forgot.submit": "Confirm identity",
    "activate.backLoginPage": "Return to login page",
    "activate.backLoginShort": "Back to login",
    "activate.titleAccent": "Activate account/",
    "activate.titleSelect": "Select your identity",
    "activate.titleConfirm": "Confirm identity",
    "activate.infoBefore": "First time using NYCU Portal? Please read the ",
    "activate.infoLink": "activation guide",
    "activate.card1Name": "Faculty / Students / Part-time assistants",
    "activate.card1Desc":
      "Undergraduate / Master's / PhD / industry programs / faculty / work-study students",
    "activate.card2Name": "Alumni",
    "activate.card2Desc": "Verified graduated alumni",
    "activate.stepConfirm": "Confirm identity",
    "activate.stepMailbox": "Apply for mailbox",
    "activate.stepPassword": "Set password",
    "activate.labelAccount": "Account",
    "activate.phAccount": "Enter account (student ID / employee ID)",
    "activate.labelBirth": "Date of birth (Gregorian)",
    "activate.labelId": "National ID / ARC number",
    "activate.phId": "Enter national ID or ARC number",
    "activate.submit": "Confirm identity",
    "help.title": "Account help",
    "help.sectionZh": "Chinese",
    "help.sectionEn": "English",
    "help.close": "Close",
  },
};

export function usePortalFlowI18n(initialLocale = "zh") {
  const [locale, setLocale] = useState(initialLocale);
  const t = (key) => FLOW_I18N[locale]?.[key] ?? FLOW_I18N.zh[key] ?? key;

  function setFlowLocale(lang) {
    if (lang === "zh" || lang === "en") {
      setLocale(lang);
    }
  }

  return { locale, t, setFlowLocale };
}
