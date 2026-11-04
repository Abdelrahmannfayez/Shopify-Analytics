export type LoginCredentials = { email: string; password: string };
export type AuthToken = { access_token: string; token_type: "bearer" };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "northstar_access_token";

export async function signIn(credentials: LoginCredentials): Promise<AuthToken> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
  if (!response.ok) {
    const body: { detail?: string } = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Unable to sign in. Check your connection and try again.");
  }
  const token = (await response.json()) as AuthToken;
  sessionStorage.setItem(TOKEN_KEY, token.access_token);
  return token;
}

export function clearSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}
