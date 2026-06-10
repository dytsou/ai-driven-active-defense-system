const defaultInit = {
  credentials: "include",
  headers: { "Content-Type": "application/json" },
};

export async function login(payload) {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    ...defaultInit,
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function fetchMe() {
  const response = await fetch("/api/v1/auth/me", {
    credentials: "include",
  });
  if (!response.ok) {
    return { ok: false, status: response.status, body: null };
  }
  const body = await response.json();
  return { ok: true, status: response.status, body };
}

// MFA send response may include delivery_target (masked recipient email).
export async function registerStart() {
  const response = await fetch("/api/v1/auth/register/start", {
    method: "POST",
    ...defaultInit,
    body: JSON.stringify({}),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function registerStatus(token) {
  const response = await fetch(`/api/v1/auth/register/status?token=${encodeURIComponent(token)}`, {
    credentials: "include",
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function registerLineStart(registrationToken) {
  const response = await fetch("/api/v1/auth/register/line/start", {
    method: "POST",
    ...defaultInit,
    body: JSON.stringify({ registration_token: registrationToken }),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function registerComplete(registrationToken, { mfaLineEnabled = true } = {}) {
  const response = await fetch("/api/v1/auth/register/complete", {
    method: "POST",
    ...defaultInit,
    body: JSON.stringify({
      registration_token: registrationToken,
      mfa_line_enabled: mfaLineEnabled,
    }),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function updateMfaPreferences({ mfaLineEnabled }) {
  const response = await fetch("/api/v1/auth/me/mfa", {
    method: "PATCH",
    ...defaultInit,
    body: JSON.stringify({ mfa_line_enabled: mfaLineEnabled }),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function mfaSend(challengeId) {
  const response = await fetch("/api/v1/auth/mfa/send", {
    method: "POST",
    ...defaultInit,
    body: JSON.stringify({ challenge_id: challengeId }),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function mfaVerify(challengeId, otp) {
  const response = await fetch("/api/v1/auth/mfa/verify", {
    method: "POST",
    ...defaultInit,
    body: JSON.stringify({ challenge_id: challengeId, otp }),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

export async function fetchAdminEvents() {
  const response = await fetch("/admin/api/events", {
    credentials: "include",
  });
  if (!response.ok) {
    return { ok: false, status: response.status, events: [] };
  }
  const data = await response.json();
  return { ok: true, status: response.status, events: data.events || [] };
}

export async function fetchAdminReport(hours = 24) {
  const response = await fetch(`/admin/api/report?hours=${encodeURIComponent(hours)}`, {
    credentials: "include",
  });
  if (!response.ok) {
    return { ok: false, status: response.status, body: null };
  }
  const body = await response.json();
  return { ok: true, status: response.status, body };
}
