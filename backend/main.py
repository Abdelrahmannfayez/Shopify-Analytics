from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, Enum, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


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


class StoreConnection(Base):
    __tablename__ = "db_connection"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    shop_domain: Mapped[str] = mapped_column(String(255), unique=True)
    shopify_access_token_enc: Mapped[str] = mapped_column(Text)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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


def get_db():
    with SessionLocal() as session:
        yield session


Db = Annotated[Session, Depends(get_db)]


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not pwd_context.verify(password, user.password_hash):
        return None
    return user


def issue_token(user: User) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    claims = {"sub": str(user.id), "tenant_id": user.tenant_id, "role": user.role, "exp": expires}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def current_user(token: Annotated[str, Depends(oauth2)], db: Db) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(claims["sub"])
        tenant_id = str(claims["tenant_id"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise unauthorized from None
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True)))
    if user is None:
        raise unauthorized
    return user


UserDep = Annotated[User, Depends(current_user)]


app = FastAPI(title="Northstar Analytics API", version="0.1.0")
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


@app.get("/auth/me", response_model=CurrentUser)
def me(user: UserDep):
    return CurrentUser(id=user.id, email=user.email, tenant_id=user.tenant_id, role=user.role)


@app.get("/store/connection", response_model=StoreStatus)
def store_connection(user: UserDep, db: Db):
    # Tenant scope comes from the verified JWT subject and is always applied to data lookups.
    connection = db.scalar(select(StoreConnection).where(StoreConnection.tenant_id == user.tenant_id))
    return StoreStatus(connected=connection is not None, shop_domain=connection.shop_domain if connection else None)


@app.get("/analytics/overview")
def analytics_overview(user: UserDep):
    # Replace this typed response placeholder with Shopify Admin API aggregates for user.tenant_id.
    return {"tenant_id": user.tenant_id, "currency": "USD", "revenue": 48294.0, "orders": 1284, "average_order_value": 37.61, "conversion_rate": 3.24}
