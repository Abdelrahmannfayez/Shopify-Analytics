import os
import sys
from uuid import uuid4

from sqlalchemy import select

from main import SessionLocal, User, pwd_context


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    tenant_id = os.environ.get("TENANT_ID", str(uuid4())).strip()
    if not email or len(password) < 12:
        raise SystemExit("Set ADMIN_EMAIL and ADMIN_PASSWORD (12+ characters) before running.")
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise SystemExit("That email already has an account; use the admin team endpoint to manage it.")
        db.add(User(email=email, password_hash=pwd_context.hash(password), tenant_id=tenant_id, role="admin", is_active=True))
        db.commit()
    print(f"Admin account created for {email} in tenant {tenant_id}.")


if __name__ == "__main__":
    main()
