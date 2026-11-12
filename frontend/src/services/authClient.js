// Authentication client.
//
// The access token (15 minutes) lives ONLY in this module's memory: never in localStorage/sessionStorage, so a
// script injected into the page cannot read it from storage. The long-lived refresh token is an HttpOnly cookie
// that JavaScript cannot see; the browser sends it to /api/auth/refresh on its own.

const API_BASE = (import.meta.env?.VITE_API_BASE || "").replace(/\/+$/, "");
const CSRF = { "X-Kabisado-Request": "1" };

let accessToken = null;
let currentUser = null;
let refreshPromise = null;
const listeners = new Set();

function notify(user) {
  currentUser = user;
  listeners.forEach((cb) => {
    try {
      cb(user);
    } catch {
      /* a broken listener must not break auth */
    }
  });
}

function setSession(token, user) {
  accessToken = token;
  notify(user);
}

function clearSession() {
  accessToken = null;
  notify(null);
}

async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(" ") : data.detail;
    const err = new Error(detail || "Something went wrong. Please try again.");
    err.status = res.status;
    err.retryAfter = Number(res.headers.get("Retry-After")) || null;
    throw err;
  }
  return data;
}

/** One refresh round trip. Returns true when we hold a fresh access token. */
async function doRefresh() {
  let res;
  try {
    res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: CSRF,
      credentials: "same-origin",
    });
  } catch {
    return false; // offline or server waking up: stay signed in locally and let the caller retry later
  }
  if (res.ok) {
    const data = await res.json();
    setSession(data.access_token, data.user);
    return true;
  }
  if (res.status === 401 || res.status === 403) clearSession(); // the session is really over
  return false;
}

/** Single-flight: concurrent callers (and, with Web Locks, other tabs) share one refresh. */
function refresh() {
  if (!refreshPromise) {
    const run = () => doRefresh();
    const locked =
      typeof navigator !== "undefined" && navigator.locks?.request
        ? navigator.locks.request("kabisado-refresh", run)
        : run();
    refreshPromise = Promise.resolve(locked).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function withAuth(options, token) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  return { ...options, headers, credentials: options.credentials || "same-origin" };
}

/** fetch() plus the bearer token; on a 401 refresh once and retry once. */
async function authFetch(url, options = {}) {
  const res = await fetch(url, withAuth(options, accessToken));
  if (res.status !== 401) return res;
  const staleToken = accessToken;
  const ok = await refresh();
  if (!ok) return res;
  if (accessToken === staleToken) return res; // nothing new to retry with
  return fetch(url, withAuth(options, accessToken)); // whatever this returns is final: no second refresh
}

const authClient = {
  async register({ displayName, username, password, confirmPassword }) {
    const data = await postJson("/api/auth/register", {
      display_name: displayName,
      username,
      password,
      confirm_password: confirmPassword,
    });
    setSession(data.access_token, data.user);
    return { user: data.user, recoveryCode: data.recovery_code };
  },

  async login({ username, password }) {
    const data = await postJson("/api/auth/login", { username, password });
    setSession(data.access_token, data.user);
    return data.user;
  },

  async recover({ username, recoveryCode, newPassword, confirmPassword }) {
    const data = await postJson("/api/auth/recover", {
      username,
      recovery_code: recoveryCode,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    setSession(data.access_token, data.user);
    return { user: data.user, recoveryCode: data.recovery_code };
  },

  async logout() {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, { method: "POST", headers: CSRF, credentials: "same-origin" });
    } catch {
      /* offline: we still sign out locally; the server session expires on its own */
    }
    clearSession();
  },

  /** Called once when the app opens: turns the refresh cookie into an access token. */
  async restoreSession() {
    return (await refresh()) ? currentUser : null;
  },

  getAccessToken: () => accessToken,

  onAuthChange(cb) {
    listeners.add(cb);
    return () => listeners.delete(cb);
  },

  authFetch,
};

export default authClient;
export { authFetch };
