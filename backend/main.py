import re
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, DateTime, Enum, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    token_encryption_key: str = ""
    shopify_api_version: str = "2026-10"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
ALLOWED_ROLES = ("admin", "analyst", "viewer")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users_master"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(Enum("admin", "analyst", "viewer", name="user_role"), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(default=0)


class StoreConnection(Base):
    __tablename__ = "db_connection"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    shop_domain: Mapped[str] = mapped_column(String(255), unique=True)
    shopify_access_token_enc: Mapped[str] = mapped_column(Text)
    shopify_refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(String(1000), default="")
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StoreAlertState(Base):
    __tablename__ = "store_alert_states"
    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class CurrentUser(BaseModel):
    id: int
    email: EmailStr
    tenant_id: str
    role: Literal["admin", "analyst", "viewer"]


class StoreStatus(BaseModel):
    connected: bool
    shop_domain: str | None = None
    scopes: list[str] = Field(default_factory=list)


class TeamMemberCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Literal["analyst", "viewer"]


class ShopifyTokenExchange(BaseModel):
    id_token: str = Field(min_length=20, max_length=8192)


def get_db():
    with SessionLocal() as session:
        yield session


Db = Annotated[Session, Depends(get_db)]


def encrypt_secret(value: str) -> str:
    if not settings.token_encryption_key:
        raise HTTPException(status_code=503, detail="Token encryption is not configured")
    try:
        return Fernet(settings.token_encryption_key.encode()).encrypt(value.encode()).decode()
    except (ValueError, TypeError):
        raise HTTPException(status_code=503, detail="Token encryption key is invalid") from None


def decrypt_secret(value: str) -> str:
    if not settings.token_encryption_key:
        raise HTTPException(status_code=503, detail="Token encryption is not configured")
    try:
        return Fernet(settings.token_encryption_key.encode()).decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        raise HTTPException(status_code=503, detail="Stored Shopify credentials cannot be decrypted") from None


def percent_points(value: object) -> float:
    raw = str(value or "0").strip()
    if raw.endswith("%"):
        return float(raw[:-1])
    return float(raw) * 100


def fraction(value: object) -> float:
    raw = str(value or "0").strip()
    if raw.endswith("%"):
        return float(raw[:-1]) / 100
    return float(raw)


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not pwd_context.verify(password, user.password_hash):
        return None
    return user


def issue_token(user: User) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    claims = {"sub": str(user.id), "tenant_id": user.tenant_id, "ver": user.token_version, "exp": expires}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def current_user(token: Annotated[str, Depends(oauth2)], db: Db) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(claims["sub"])
        tenant_id = str(claims["tenant_id"])
        token_version = int(claims["ver"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise unauthorized from None
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True)))
    if user is None or user.token_version != token_version:
        raise unauthorized
    return user


UserDep = Annotated[User, Depends(current_user)]


def require_roles(*allowed: str):
    def role_guard(user: UserDep) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot perform this action")
        return user
    return role_guard


def verified_shopify_claims(id_token: str) -> tuple[dict[str, object], str]:
    if not settings.shopify_client_id or not settings.shopify_client_secret:
        raise HTTPException(status_code=503, detail="Shopify app credentials are not configured")
    try:
        claims = jwt.decode(id_token, settings.shopify_client_secret, algorithms=["HS256"], audience=settings.shopify_client_id)
        issuer = urlparse(str(claims["iss"]))
        destination = urlparse(str(claims["dest"]))
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid Shopify session token", headers={"X-Shopify-Retry-Invalid-Session-Request": "1"}) from None
    hostname = (destination.hostname or "").lower()
    if issuer.scheme != "https" or issuer.hostname is None or issuer.hostname.lower() != hostname or re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", hostname) is None or destination.scheme != "https":
        raise HTTPException(status_code=401, detail="Shopify token shop does not match", headers={"X-Shopify-Retry-Invalid-Session-Request": "1"})
    return claims, hostname


async def request_shopify_token(shop_domain: str, values: dict[str, str]) -> dict[str, object]:
    endpoint = f"https://{shop_domain}/admin/oauth/access_token"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(endpoint, data=values)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach Shopify token service") from None
    if not response.is_success:
        raise HTTPException(status_code=502, detail="Shopify rejected the token request")
    return response.json()


async def ensure_fresh_token(db: Session, connection: StoreConnection) -> str:
    now = datetime.now(timezone.utc)
    expires_at = connection.access_token_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at is None or expires_at > now + timedelta(minutes=5):
        return decrypt_secret(connection.shopify_access_token_enc)
    refresh_token = connection.shopify_refresh_token_enc
    refresh_expires = connection.refresh_token_expires_at
    if refresh_expires is not None and refresh_expires.tzinfo is None:
        refresh_expires = refresh_expires.replace(tzinfo=timezone.utc)
    if refresh_expires is not None and refresh_expires <= now + timedelta(minutes=1):
        raise HTTPException(status_code=401, detail="Shopify refresh token expired; reconnect the store")
    if not refresh_token or not settings.shopify_client_id or not settings.shopify_client_secret:
        raise HTTPException(status_code=401, detail="Shopify token expired; reconnect the store")
    payload = await request_shopify_token(connection.shop_domain, {
        "client_id": settings.shopify_client_id,
        "client_secret": settings.shopify_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": decrypt_secret(refresh_token),
    })
    access = str(payload.get("access_token", ""))
    new_refresh = str(payload.get("refresh_token", ""))
    if not access or not new_refresh:
        raise HTTPException(status_code=502, detail="Shopify returned an incomplete refresh response")
    connection.shopify_access_token_enc = encrypt_secret(access)
    connection.shopify_refresh_token_enc = encrypt_secret(new_refresh)
    connection.access_token_expires_at = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
    refresh_lifetime = payload.get("refresh_token_expires_in")
    if refresh_lifetime is not None:
        connection.refresh_token_expires_at = now + timedelta(seconds=int(refresh_lifetime))
    db.commit()
    return access


async def shopify_graphql(db: Session, user: User, query: str) -> dict[str, object]:
    connection = db.scalar(select(StoreConnection).where(StoreConnection.tenant_id == user.tenant_id))
    if connection is None:
        raise HTTPException(status_code=409, detail="Connect a Shopify store before requesting analytics")
    token = await ensure_fresh_token(db, connection)
    endpoint = f"https://{connection.shop_domain}/admin/api/{settings.shopify_api_version}/graphql.json"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(endpoint, json={"query": query}, headers={"X-Shopify-Access-Token": token})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach the Shopify Admin API") from None
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Shopify rejected the store token; reconnect the store")
    if not response.is_success:
        raise HTTPException(status_code=502, detail="Shopify Admin API request failed")
    body = response.json()
    if body.get("errors"):
        raise HTTPException(status_code=502, detail={"message": "Shopify analytics query failed", "errors": body["errors"]})
    return body.get("data", {})


app = FastAPI(title="Northstar Analytics API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Db):
    user = authenticate(db, payload.email.lower(), payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect")
    return TokenResponse(access_token=issue_token(user))


@app.post("/auth/logout")
def logout(user: UserDep, db: Db):
    user.token_version += 1
    db.commit()
    return {"ok": True}


@app.get("/auth/me", response_model=CurrentUser)
def me(user: UserDep):
    return CurrentUser(id=user.id, email=user.email, tenant_id=user.tenant_id, role=user.role)


@app.post("/shopify/token-exchange")
async def shopify_token_exchange(payload: ShopifyTokenExchange, user: Annotated[User, Depends(require_roles("admin"))], db: Db):
    claims, shop_domain = verified_shopify_claims(payload.id_token)
    existing = db.scalar(select(StoreConnection).where(StoreConnection.shop_domain == shop_domain))
    if existing is not None and existing.tenant_id != user.tenant_id:
        raise HTTPException(status_code=409, detail="This Shopify store is connected to another account")
    payload = await request_shopify_token(shop_domain, {
        "client_id": settings.shopify_client_id,
        "client_secret": settings.shopify_client_secret,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": payload.id_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
        "requested_token_type": "urn:shopify:params:oauth:token-type:offline-access-token",
        "expiring": "1",
    })
    access = str(payload.get("access_token", ""))
    refresh = str(payload.get("refresh_token", ""))
    if not access or not refresh:
        raise HTTPException(status_code=502, detail="Shopify did not return expiring offline token credentials")
    connection = existing or StoreConnection(tenant_id=user.tenant_id, shop_domain=shop_domain, shopify_access_token_enc="")
    connection.shopify_access_token_enc = encrypt_secret(access)
    connection.shopify_refresh_token_enc = encrypt_secret(refresh)
    connection.access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 3600)))
    refresh_lifetime = payload.get("refresh_token_expires_in")
    connection.refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(refresh_lifetime)) if refresh_lifetime is not None else None
    connection.scopes = str(payload.get("scope", ""))
    if existing is None:
        db.add(connection)
    db.commit()
    return {"connected": True, "shop_domain": shop_domain, "tenant_id": user.tenant_id, "subject": claims.get("sub")}


@app.get("/store/connection", response_model=StoreStatus)
def store_connection(user: UserDep, db: Db):
    connection = db.scalar(select(StoreConnection).where(StoreConnection.tenant_id == user.tenant_id))
    return StoreStatus(connected=connection is not None, shop_domain=connection.shop_domain if connection else None, scopes=connection.scopes.split(",") if connection and connection.scopes else [])


@app.get("/analytics/overview")
async def analytics_overview(user: UserDep, db: Db, days: int = 7):
    if days not in (7, 30, 90):
        raise HTTPException(status_code=422, detail="days must be 7, 30, or 90")
    data = await shopify_graphql(db, user, f'''query StoreOverview {{
      shop {{ currencyCode }}
      shopifyqlQuery(query: "FROM sales, sessions SHOW total_sales, orders, average_order_value, sessions, conversion_rate TIMESERIES day SINCE -{days}d UNTIL today ORDER BY day ASC") {{
        tableData {{ columns {{ name }} rows }}
        parseErrors
        parseWarnings
      }}
    }}''')
    report = data.get("shopifyqlQuery", {})
    if report.get("parseErrors"):
        raise HTTPException(status_code=502, detail={"message": "ShopifyQL could not run the sales report", "errors": report["parseErrors"]})
    rows = report.get("tableData", {}).get("rows", [])
    series = [{"date": row.get("day"), "revenue": float(row.get("total_sales") or 0), "orders": int(row.get("orders") or 0), "sessions": int(row.get("sessions") or 0), "conversion_rate": percent_points(row.get("conversion_rate"))} for row in rows]
    revenue = sum(row["revenue"] for row in series)
    orders = sum(row["orders"] for row in series)
    sessions = sum(row["sessions"] for row in series)
    weighted_conversion = sum(row["conversion_rate"] * row["sessions"] for row in series) / sessions if sessions else None
    return {"currency": data.get("shop", {}).get("currencyCode", "USD"), "revenue": revenue, "orders": orders, "average_order_value": revenue / orders if orders else 0, "conversion_rate": weighted_conversion, "series": series, "warnings": report.get("parseWarnings", [])}


@app.get("/analytics/products")
async def top_products(user: UserDep, db: Db):
    data = await shopify_graphql(db, user, '''query ProductReport {
      shop { currencyCode }
      products(first: 100, sortKey: TITLE) { nodes { title totalInventory } }
      shopifyqlQuery(query: "FROM sales SHOW total_sales, net_items_sold GROUP BY product_title SINCE -30d ORDER BY total_sales DESC LIMIT 100") {
        tableData { rows }
        parseErrors
        parseWarnings
      }
    }''')
    report = data.get("shopifyqlQuery", {})
    if report.get("parseErrors"):
        raise HTTPException(status_code=502, detail={"message": "ShopifyQL could not run the product report", "errors": report["parseErrors"]})
    sales_rows = report.get("tableData", {}).get("rows", [])
    sales = {str(row.get("product_title", "")).casefold(): row for row in sales_rows}
    inventory_rows = data.get("products", {}).get("nodes", [])
    titles = {str(row.get("product_title", "Untitled product")) for row in sales_rows}
    titles.update(str(row.get("title", "Untitled product")) for row in inventory_rows)
    inventory = {str(row.get("title", "")).casefold(): int(row.get("totalInventory") or 0) for row in inventory_rows}
    products_data = []
    for title in titles:
        sales_row = sales.get(title.casefold(), {})
        units = int(sales_row.get("net_items_sold") or 0)
        stock = inventory.get(title.casefold(), 0)
        daily_units = max(units / 30, 0.05)
        days_left = round(stock / daily_units, 1) if stock > 0 else 0
        products_data.append({"title": title, "revenue": float(sales_row.get("total_sales") or 0), "units_sold": units, "inventory": stock, "days_of_stock": days_left, "reorder_quantity": max(0, int(daily_units * 30 - stock + 0.999)), "margin_percent": None, "status": "Dead stock" if units == 0 and stock > 100 else "Slow" if units == 0 else "Stable"})
    products_data.sort(key=lambda product: product["revenue"], reverse=True)
    for product in products_data[:max(1, len(products_data) // 4)]:
        if product["units_sold"] > 0:
            product["status"] = "Winner"
    return {"currency": data.get("shop", {}).get("currencyCode", "USD"), "products": products_data, "warnings": report.get("parseWarnings", [])}


@app.get("/analytics/orders")
async def recent_orders(user: UserDep, db: Db, limit: int = 5):
    if not 1 <= limit <= 20:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 20")
    data = await shopify_graphql(db, user, f'''query RecentOrders {{
      orders(first: {limit}, sortKey: CREATED_AT, reverse: true) {{
        nodes {{ id name createdAt displayFinancialStatus currentTotalPriceSet {{ shopMoney {{ amount currencyCode }} }} }}
      }}
    }}''')
    nodes = data.get("orders", {}).get("nodes", [])
    return {"orders": [{"id": order.get("id"), "name": order.get("name"), "created_at": order.get("createdAt"), "status": order.get("displayFinancialStatus"), "amount": float(order.get("currentTotalPriceSet", {}).get("shopMoney", {}).get("amount", 0)), "currency": order.get("currentTotalPriceSet", {}).get("shopMoney", {}).get("currencyCode", "USD")} for order in nodes]}


@app.get("/analytics/customers")
async def customer_analytics(user: UserDep, db: Db):
    data = await shopify_graphql(db, user, '''query CustomerAnalytics {
      shop { currencyCode }
      customersCount { count }
      customerSegments: shopifyqlQuery(query: "FROM customers SHOW percent_of_customers, total_amount_spent GROUP BY rfm_group") { tableData { rows } parseErrors }
      cohortMix: shopifyqlQuery(query: "FROM customers SHOW percent_of_customers GROUP BY customer_cohort_month, rfm_group ORDER BY customer_cohort_month ASC LIMIT 50") { tableData { rows } parseErrors }
      repeatRate: shopifyqlQuery(query: "FROM sales SHOW returning_customer_rate SINCE -90d UNTIL today") { tableData { rows } parseErrors }
    }''')
    segments_report = data.get("customerSegments", {})
    if segments_report.get("parseErrors"):
        raise HTTPException(status_code=502, detail={"message": "ShopifyQL could not run the customer report", "errors": segments_report["parseErrors"]})
    customer_count = int(data.get("customersCount", {}).get("count", 0))
    segment_rows = segments_report.get("tableData", {}).get("rows", [])
    segments = {"champions": 0, "loyal": 0, "at_risk": 0, "lost": 0}
    total_spend = 0.0
    for row in segment_rows:
        name = str(row.get("rfm_group", "")).casefold()
        share = fraction(row.get("percent_of_customers"))
        count = round(customer_count * share)
        total_spend += float(row.get("total_amount_spent") or 0)
        if name == "champions":
            segments["champions"] += count
        elif name == "loyal":
            segments["loyal"] += count
        elif name == "needs attention":
            segments["at_risk"] += count
        elif name == "at risk":
            segments["lost"] += count
    cohort_report = data.get("cohortMix", {})
    cohort_rows = cohort_report.get("tableData", {}).get("rows", []) if not cohort_report.get("parseErrors") else []
    cohort_mix = [{"cohort_month": str(row.get("customer_cohort_month", "")), "segment": str(row.get("rfm_group", "Unknown")), "share": fraction(row.get("percent_of_customers"))} for row in cohort_rows]
    repeat_report = data.get("repeatRate", {})
    repeat_rows = repeat_report.get("tableData", {}).get("rows", [])
    if repeat_report.get("parseErrors") or not repeat_rows:
        repeat_rate = None
    else:
        repeat_rate = percent_points(repeat_rows[0].get("returning_customer_rate"))
    return {"currency": data.get("shop", {}).get("currencyCode", "USD"), "total_customers": customer_count, "segments": segments, "repeat_purchase_rate": repeat_rate, "lifetime_value": total_spend / customer_count if customer_count else 0, "cohort_mix": cohort_mix}


@app.get("/analytics/forecast")
async def sales_forecast(user: UserDep, db: Db):
    data = await shopify_graphql(db, user, '''query SalesForecast {
      shop { currencyCode }
      shopifyqlQuery(query: "FROM sales SHOW total_sales TIMESERIES day SINCE -90d UNTIL today ORDER BY day ASC") { tableData { rows } parseErrors }
    }''')
    report = data.get("shopifyqlQuery", {})
    if report.get("parseErrors"):
        raise HTTPException(status_code=502, detail={"message": "ShopifyQL could not run the forecast base report", "errors": report["parseErrors"]})
    rows = report.get("tableData", {}).get("rows", [])
    actual = [{"date": str(row.get("day", "")), "revenue": float(row.get("total_sales") or 0)} for row in rows]
    tail = actual[-30:]
    values = [row["revenue"] for row in tail]
    count = len(values)
    mean_x = (count - 1) / 2 if count else 0
    mean_y = sum(values) / count if count else 0
    variance_x = sum((index - mean_x) ** 2 for index in range(count))
    slope = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values)) / variance_x if variance_x else 0
    residuals = [value - (mean_y + slope * (index - mean_x)) for index, value in enumerate(values)]
    spread = (sum(error * error for error in residuals) / max(1, count - 2)) ** 0.5
    forecast = []
    today = datetime.now(timezone.utc).date()
    for step in range(1, 31):
        prediction = max(0, mean_y + slope * ((count - 1) + step - mean_x))
        forecast.append({"date": str(today + timedelta(days=step)), "revenue": prediction, "lower": max(0, prediction - 1.5 * spread), "upper": prediction + 1.5 * spread})
    return {"currency": data.get("shop", {}).get("currencyCode", "USD"), "actual": actual[-30:], "forecast": forecast, "expected_revenue_7d": sum(row["revenue"] for row in forecast[:7]), "expected_revenue_30d": sum(row["revenue"] for row in forecast), "method": "30-day linear trend with residual-based band"}


@app.get("/analytics/alerts")
async def store_alerts(user: UserDep, db: Db):
    data = await shopify_graphql(db, user, '''query StoreAlerts {
      shopifyqlQuery(query: "FROM sales SHOW total_sales TIMESERIES day SINCE -14d UNTIL today ORDER BY day ASC") { tableData { rows } parseErrors }
      products(first: 100, sortKey: TITLE) { nodes { title totalInventory } }
      productSales: shopifyqlQuery(query: "FROM sales SHOW net_items_sold GROUP BY product_title SINCE -30d UNTIL today LIMIT 100") { tableData { rows } parseErrors }
    }''')
    sales_report = data.get("shopifyqlQuery", {})
    if sales_report.get("parseErrors"):
        raise HTTPException(status_code=502, detail="Shopify could not generate the sales anomaly report")
    daily_rows = sales_report.get("tableData", {}).get("rows", [])
    recent = sum(float(row.get("total_sales") or 0) for row in daily_rows[-7:])
    previous = sum(float(row.get("total_sales") or 0) for row in daily_rows[-14:-7])
    alerts = []
    now = datetime.now(timezone.utc).isoformat()
    if previous > 0 and recent < previous * 0.9:
        change = round((recent / previous - 1) * 100, 1)
        title = "Sales are trending below the previous week"
        alert_id = hashlib.sha256(f"{title}:{datetime.now(timezone.utc).date()}".encode()).hexdigest()[:24]
        alerts.append({"id": alert_id, "severity": "Warning", "title": title, "detail": f"Revenue is down {abs(change)}% week over week.", "created_at": now})
    product_sales = {str(row.get("product_title", "")).casefold(): int(row.get("net_items_sold") or 0) for row in data.get("productSales", {}).get("tableData", {}).get("rows", [])}
    for product in data.get("products", {}).get("nodes", []):
        title = str(product.get("title", "Product"))
        stock = int(product.get("totalInventory") or 0)
        daily = max(product_sales.get(title.casefold(), 0) / 30, 0.05)
        days_left = stock / daily if stock else 0
        if days_left <= 7:
            alert_title = f"{title} is running low"
            alert_id = hashlib.sha256(f"{alert_title}:{datetime.now(timezone.utc).date()}".encode()).hexdigest()[:24]
            alerts.append({"id": alert_id, "severity": "Critical" if days_left <= 3 else "Warning", "title": alert_title, "detail": f"About {round(days_left)} days of stock remain.", "created_at": now})
    alerts = alerts[:20]
    states = {state.alert_id for state in db.scalars(select(StoreAlertState).where(StoreAlertState.tenant_id == user.tenant_id, StoreAlertState.alert_id.in_([alert["id"] for alert in alerts]))).all()} if alerts else set()
    return {"alerts": [{**alert, "resolved": alert["id"] in states} for alert in alerts]}


@app.post("/analytics/alerts/{alert_id}/resolve")
async def resolve_store_alert(alert_id: str, user: Annotated[User, Depends(require_roles("admin", "analyst"))], db: Db):
    current_alerts = await store_alerts(user, db)
    if not any(alert["id"] == alert_id for alert in current_alerts["alerts"]):
        raise HTTPException(status_code=404, detail="This alert is no longer active")
    state = db.get(StoreAlertState, (user.tenant_id, alert_id))
    if state is None:
        db.add(StoreAlertState(tenant_id=user.tenant_id, alert_id=alert_id))
        db.commit()
    return {"id": alert_id, "resolved": True}


@app.get("/team/users", response_model=list[CurrentUser])
def list_team_users(user: Annotated[User, Depends(require_roles("admin"))], db: Db):
    members = db.scalars(select(User).where(User.tenant_id == user.tenant_id).order_by(User.id)).all()
    return [CurrentUser(id=member.id, email=member.email, tenant_id=member.tenant_id, role=member.role) for member in members]


@app.post("/team/users", response_model=CurrentUser, status_code=201)
def create_team_user(payload: TeamMemberCreate, user: Annotated[User, Depends(require_roles("admin"))], db: Db):
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account already exists for this email")
    member = User(email=email, password_hash=pwd_context.hash(payload.password), tenant_id=user.tenant_id, role=payload.role, is_active=True)
    db.add(member)
    db.commit()
    db.refresh(member)
    return CurrentUser(id=member.id, email=member.email, tenant_id=member.tenant_id, role=member.role)
