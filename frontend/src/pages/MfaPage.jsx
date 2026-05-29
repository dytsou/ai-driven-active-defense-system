import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { mfaSend, mfaVerify } from "../api.js";

export default function MfaPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const challengeId = searchParams.get("challenge_id") || "";
  const [otp, setOtp] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  if (!challengeId) {
    return (
      <div className="page">
        <h1>MFA Verification</h1>
        <p className="status error">Missing challenge. Please sign in again.</p>
      </div>
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
      setStatus("Sending...");
      const { body } = await mfaSend(challengeId);
      setStatus(body.message || body.status);
    });
  }

  async function handleVerify() {
    await runOnce(async () => {
      setStatus("Verifying...");
      const { body } = await mfaVerify(challengeId, otp);
      if (body.status === "success") {
        navigate("/admin/events");
        return;
      }
      setStatus(body.message || body.status);
    });
  }

  return (
    <div className="page">
      <h1>Email Verification</h1>
      <p>Enter the 6-digit code sent to your email.</p>
      <label>
        OTP
        <input
          value={otp}
          onChange={(e) => setOtp(e.target.value)}
          maxLength={6}
          placeholder="000000"
          inputMode="numeric"
          disabled={busy}
        />
      </label>
      <button type="button" className="secondary" onClick={handleSend} disabled={busy}>
        Send code
      </button>
      <button type="button" onClick={handleVerify} disabled={busy}>
        Verify
      </button>
      {status && <p className="status">{status}</p>}
    </div>
  );
}
