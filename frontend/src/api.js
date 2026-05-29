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
