const DOMAIN = process.env.NEXT_PUBLIC_COGNITO_DOMAIN?.replace(/\/$/, "") ?? "";
const CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";
const REDIRECT_URI = process.env.NEXT_PUBLIC_COGNITO_REDIRECT_URI ?? "";
const LOGOUT_URI = process.env.NEXT_PUBLIC_COGNITO_LOGOUT_URI ?? "";

const VERIFIER_KEY = "portfolioguard.oauth.verifier";
const STATE_KEY = "portfolioguard.oauth.state";
const TOKEN_KEY = "portfolioguard.oauth.access_token";
const EXPIRY_KEY = "portfolioguard.oauth.expires_at";
const RETURN_KEY = "portfolioguard.oauth.return_to";

function encode(bytes: Uint8Array) {
  let value = "";
  for (const byte of bytes) value += String.fromCharCode(byte);
  return btoa(value).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function randomValue(length = 32) {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return encode(bytes);
}

export function authConfigured() {
  return Boolean(DOMAIN && CLIENT_ID && REDIRECT_URI && LOGOUT_URI);
}

export function getAccessToken() {
  if (typeof window === "undefined" || !authConfigured()) return null;
  const token = sessionStorage.getItem(TOKEN_KEY);
  const expiresAt = Number(sessionStorage.getItem(EXPIRY_KEY) ?? 0);
  if (!token || !expiresAt || Date.now() >= expiresAt - 30_000) {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(EXPIRY_KEY);
    return null;
  }
  return token;
}

export async function beginLogin() {
  if (!authConfigured()) throw new Error("Demo authentication is not configured");
  const verifier = randomValue(48);
  const state = randomValue();
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);
  sessionStorage.setItem(RETURN_KEY, `${window.location.pathname}${window.location.search}`);
  const query = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    scope: "openid email",
    state,
    code_challenge_method: "S256",
    code_challenge: encode(new Uint8Array(digest)),
  });
  // Cognito is an external OAuth endpoint, not an internal Next.js route.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = `${DOMAIN}/oauth2/authorize?${query}`;
}

export async function completeLogin(code: string, state: string) {
  if (!authConfigured()) throw new Error("Demo authentication is not configured");
  const expectedState = sessionStorage.getItem(STATE_KEY);
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
  if (!expectedState || expectedState !== state || !verifier) {
    throw new Error("The authentication response could not be verified");
  }
  const response = await fetch(`${DOMAIN}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: CLIENT_ID,
      code,
      redirect_uri: REDIRECT_URI,
      code_verifier: verifier,
    }),
  });
  if (!response.ok) throw new Error("Authentication token exchange failed");
  const payload = (await response.json()) as { access_token?: string; expires_in?: number };
  if (!payload.access_token || !payload.expires_in) {
    throw new Error("Authentication server returned an invalid token response");
  }
  sessionStorage.setItem(TOKEN_KEY, payload.access_token);
  sessionStorage.setItem(EXPIRY_KEY, String(Date.now() + payload.expires_in * 1000));
  const returnTo = sessionStorage.getItem(RETURN_KEY) ?? "/dashboard";
  sessionStorage.removeItem(RETURN_KEY);
  return returnTo.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/dashboard";
}

export function logout() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EXPIRY_KEY);
  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
  sessionStorage.removeItem(RETURN_KEY);
  if (!authConfigured()) {
    window.history.replaceState(null, "", "/");
    window.location.reload();
    return;
  }
  const query = new URLSearchParams({ client_id: CLIENT_ID, logout_uri: LOGOUT_URI });
  // Cognito is an external OAuth endpoint, not an internal Next.js route.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = `${DOMAIN}/logout?${query}`;
}

export function apiAuthorizationHeader(): Record<string, string> {
  if (!authConfigured()) return {};
  const token = getAccessToken();
  if (!token) throw new Error("Authentication required. Sign in to use the AWS demo.");
  return { Authorization: `Bearer ${token}` };
}
