import { beforeEach, describe, expect, it, vi } from "vitest";

const json = (status, body = {}) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const USER = { public_id: "u1", display_name: "Ana", username: "ana", role: "student" };

let storage;
let fetchMock;
let authClient;
let refreshCalls;

function installStorage() {
  const make = () => ({ setItem: vi.fn(), getItem: vi.fn(() => null), removeItem: vi.fn() });
  storage = { local: make(), session: make() };
  vi.stubGlobal("localStorage", storage.local);
  vi.stubGlobal("sessionStorage", storage.session);
}

async function load(handler) {
  refreshCalls = 0;
  fetchMock = vi.fn(async (url, options = {}) => {
    if (String(url).endsWith("/api/auth/refresh")) refreshCalls += 1;
    return handler(String(url), options);
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.resetModules();
  authClient = (await import("./authClient.js")).default;
}

async function signIn() {
  await authClient.login({ username: "ana", password: "pw" });
}

beforeEach(() => {
  installStorage();
});

const loginThen = (rest) => (url, options) => {
  if (url.endsWith("/api/auth/login")) return json(200, { access_token: "old", user: USER });
  return rest(url, options);
};

describe("token storage", () => {
  it("keeps the access token in memory only", async () => {
    await load(loginThen(() => json(200)));
    await signIn();
    expect(authClient.getAccessToken()).toBe("old");
    expect(storage.local.setItem).not.toHaveBeenCalled();
    expect(storage.session.setItem).not.toHaveBeenCalled();
  });

  it("sends refresh and logout calls with the CSRF header and same-origin credentials", async () => {
    await load(
      loginThen((url) => {
        if (url.endsWith("/api/auth/refresh")) return json(200, { access_token: "new", user: USER });
        return json(204);
      })
    );
    await authClient.restoreSession();
    await authClient.logout();
    for (const [url, options] of fetchMock.mock.calls) {
      expect(options.method).toBe("POST");
      expect(options.headers["X-Kabisado-Request"]).toBe("1");
      expect(options.credentials).toBe("same-origin");
      expect(url).toMatch(/\/api\/auth\/(refresh|logout)$/);
    }
  });
});

describe("authFetch", () => {
  it("adds the bearer token", async () => {
    await load(loginThen(() => json(200, [])));
    await signIn();
    await authClient.authFetch("/api/documents");
    expect(fetchMock.mock.calls.at(-1)[1].headers.Authorization).toBe("Bearer old");
  });

  it("on 401 refreshes once and retries successfully", async () => {
    await load(
      loginThen((url, options) => {
        if (url.endsWith("/api/auth/refresh")) return json(200, { access_token: "new", user: USER });
        return options.headers.Authorization === "Bearer new" ? json(200, ["ok"]) : json(401);
      })
    );
    await signIn();
    const res = await authClient.authFetch("/api/documents");
    expect(res.status).toBe(200);
    expect(refreshCalls).toBe(1);
    expect(authClient.getAccessToken()).toBe("new");
  });

  it("five concurrent 401s share exactly one refresh call", async () => {
    await load(
      loginThen(async (url, options) => {
        if (url.endsWith("/api/auth/refresh")) {
          await new Promise((r) => setTimeout(r, 20));
          return json(200, { access_token: "new", user: USER });
        }
        return options.headers.Authorization === "Bearer new" ? json(200, []) : json(401);
      })
    );
    await signIn();
    const results = await Promise.all(Array.from({ length: 5 }, () => authClient.authFetch("/api/documents")));
    expect(results.map((r) => r.status)).toEqual([200, 200, 200, 200, 200]);
    expect(refreshCalls).toBe(1);
  });

  it("a failed refresh notifies listeners with null, returns the 401 and does not loop", async () => {
    await load(
      loginThen((url) => (url.endsWith("/api/auth/refresh") ? json(401, { detail: "expired" }) : json(401)))
    );
    const seen = [];
    authClient.onAuthChange((u) => seen.push(u));
    await signIn();
    const res = await authClient.authFetch("/api/documents");
    expect(res.status).toBe(401);
    expect(refreshCalls).toBe(1);
    expect(fetchMock.mock.calls.filter(([u]) => u.endsWith("/api/documents"))).toHaveLength(1);
    expect(seen.at(-1)).toBeNull();
    expect(authClient.getAccessToken()).toBeNull();
  });

  it("a retry that is still 401 is returned, not retried again", async () => {
    await load(
      loginThen((url) =>
        url.endsWith("/api/auth/refresh") ? json(200, { access_token: "new", user: USER }) : json(401)
      )
    );
    await signIn();
    const res = await authClient.authFetch("/api/documents");
    expect(res.status).toBe(401);
    expect(refreshCalls).toBe(1);
  });

  it("a network error during refresh does not sign the user out", async () => {
    await load(
      loginThen((url) => {
        if (url.endsWith("/api/auth/refresh")) throw new TypeError("network down");
        return json(401);
      })
    );
    const seen = [];
    authClient.onAuthChange((u) => seen.push(u));
    await signIn();
    const res = await authClient.authFetch("/api/documents");
    expect(res.status).toBe(401);
    expect(seen.filter((u) => u === null)).toHaveLength(0);
    expect(authClient.getAccessToken()).toBe("old");
  });
});

describe("session lifecycle", () => {
  it("restoreSession returns the user from the refresh cookie, or null", async () => {
    await load(() => json(200, { access_token: "t", user: USER }));
    expect(await authClient.restoreSession()).toEqual(USER);
    await load(() => json(401));
    expect(await authClient.restoreSession()).toBeNull();
  });

  it("logout clears the token even when the network fails", async () => {
    await load(
      loginThen((url) => {
        if (url.endsWith("/api/auth/logout")) throw new TypeError("offline");
        return json(200);
      })
    );
    const seen = [];
    authClient.onAuthChange((u) => seen.push(u));
    await signIn();
    await expect(authClient.logout()).resolves.toBeUndefined();
    expect(authClient.getAccessToken()).toBeNull();
    expect(seen.at(-1)).toBeNull();
  });

  it("register and recover return the one-time recovery code and sign the user in", async () => {
    await load((url) =>
      json(url.endsWith("/register") ? 201 : 200, { access_token: "t", user: USER, recovery_code: "AAAA-BBBB" })
    );
    const reg = await authClient.register({ displayName: "Ana", username: "ana", password: "p", confirmPassword: "p" });
    expect(reg).toEqual({ user: USER, recoveryCode: "AAAA-BBBB" });
    expect(authClient.getAccessToken()).toBe("t");
    const rec = await authClient.recover({
      username: "ana", recoveryCode: "AAAA", newPassword: "p", confirmPassword: "p",
    });
    expect(rec.recoveryCode).toBe("AAAA-BBBB");
    const body = JSON.parse(fetchMock.mock.calls.at(-1)[1].body);
    expect(body).toEqual({ username: "ana", recovery_code: "AAAA", new_password: "p", confirm_password: "p" });
  });

  it("login errors carry the server message and status, and leave no token", async () => {
    await load(() => json(429, { detail: "Too many attempts." }));
    await expect(authClient.login({ username: "a", password: "b" })).rejects.toMatchObject({
      message: "Too many attempts.",
      status: 429,
    });
    expect(authClient.getAccessToken()).toBeNull();
  });

  it("onAuthChange returns an unsubscribe function", async () => {
    await load(loginThen(() => json(200)));
    const cb = vi.fn();
    const off = authClient.onAuthChange(cb);
    off();
    await signIn();
    expect(cb).not.toHaveBeenCalled();
  });
});
