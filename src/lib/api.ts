export type LoginCredentials = { email: string; password: string };
export type AuthToken = { access_token: string; token_type: "bearer" };
export type AppUser = { id: number; email: string; tenant_id: string; role: "admin" | "analyst" | "viewer" };
export type Overview = {
  currency: string;
  revenue: number;
  orders: number;
  average_order_value: number;
  conversion_rate: number | null;
  series: { date: string; revenue: number; orders: number }[];
  warnings: string[];
};
export type StoreConnection = { connected: boolean; shop_domain: string | null; scopes: string[] };
export type ProductSales = { title: string; revenue: number; units_sold: number; inventory: number; days_of_stock: number; reorder_quantity: number; margin_percent: number | null; status: "Winner" | "Stable" | "Slow" | "Dead stock" };
export type RecentOrder = { id: string; name: string; created_at: string; status: string; amount: number; currency: string };
export type CustomerAnalytics = { currency: string; total_customers: number; segments: { champions: number; loyal: number; at_risk: number; lost: number }; repeat_purchase_rate: number | null; lifetime_value: number; cohort_mix: { cohort_month: string; segment: string; share: number }[] };
export type SalesForecast = { currency: string; actual: { date: string; revenue: number }[]; forecast: { date: string; revenue: number; lower: number; upper: number }[]; expected_revenue_7d: number; expected_revenue_30d: number; method: string };
export type StoreAlert = { id: string; severity: "Critical" | "Warning" | "Info"; title: string; detail: string; created_at: string; resolved: boolean };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "northstar_access_token";

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...init.headers },
  });
  if (!response.ok) {
    const body: { detail?: string } = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

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

export function getSessionToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getCurrentUser(token: string): Promise<AppUser> {
  return request<AppUser>("/auth/me", token);
}

export function getOverview(token: string, days: 7 | 30 | 90): Promise<Overview> {
  return request<Overview>(`/analytics/overview?days=${days}`, token);
}

export async function getTopProducts(token: string): Promise<ProductSales[]> {
  const data = await request<{ products: ProductSales[] }>("/analytics/products", token);
  return data.products;
}

export async function getCustomerAnalytics(token: string): Promise<CustomerAnalytics> {
  return request<CustomerAnalytics>("/analytics/customers", token);
}

export async function getSalesForecast(token: string): Promise<SalesForecast> {
  return request<SalesForecast>("/analytics/forecast", token);
}

export async function getStoreAlerts(token: string): Promise<StoreAlert[]> {
  const data = await request<{ alerts: StoreAlert[] }>("/analytics/alerts", token);
  return data.alerts;
}

export function resolveStoreAlert(token: string, alertId: string): Promise<{ id: string; resolved: boolean }> {
  return request(`/analytics/alerts/${encodeURIComponent(alertId)}/resolve`, token, { method: "POST" });
}

export async function getRecentOrders(token: string): Promise<RecentOrder[]> {
  const data = await request<{ orders: RecentOrder[] }>("/analytics/orders?limit=4", token);
  return data.orders;
}

export function getStoreConnection(token: string): Promise<StoreConnection> {
  return request<StoreConnection>("/store/connection", token);
}

export function connectShopify(token: string, idToken: string): Promise<{ connected: boolean; shop_domain: string }> {
  return request("/shopify/token-exchange", token, { method: "POST", body: JSON.stringify({ id_token: idToken }) });
}

export async function signOut(token: string | null): Promise<void> {
  try {
    if (token) {
      await request<{ ok: boolean }>("/auth/logout", token, { method: "POST" });
    }
  } catch {
    // Clearing the browser session is the important part of sign-out.
  } finally {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}
