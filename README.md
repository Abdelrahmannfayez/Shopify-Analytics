# Northstar Shopify Analytics

A bilingual English / Arabic Shopify analytics dashboard built with Next.js App Router, TypeScript, Tailwind CSS, ECharts and lucide-react. The FastAPI service uses MySQL, tenant-scoped JWT sessions, role checks and Shopify's embedded app token-exchange flow.

## Dashboard

```bash
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_SHOPIFY_CLIENT_ID` in `.env.local`. The Shopify client ID is public; keep the client secret only in the backend environment. Without an API session, the dashboard remains in sample-data preview mode. After sign-in and store connection, revenue, order counts, conversion, sales charts, top products and recent orders load from tenant-scoped Shopify API endpoints.

## FastAPI and MySQL

1. Create the `master` database and tables with `backend/schema.sql`. For an existing database created from the earlier schema, apply `backend/migrations/001_shopify_token_rotation.sql` once.
2. Copy `backend/.env.example` to `backend/.env` and set the MySQL URL, a long random `JWT_SECRET`, Shopify app client ID and secret, and a Fernet `TOKEN_ENCRYPTION_KEY`.
3. Generate a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and put the result in the backend environment. Shopify access and refresh tokens are encrypted before storage.
4. Install dependencies and provision the first tenant admin:

   ```powershell
   cd backend
   pip install -r requirements.txt
   $env:ADMIN_EMAIL = "admin@example.com"
   $env:ADMIN_PASSWORD = "use-a-long-unique-password"
   python bootstrap_admin.py
   uvicorn main:app --reload
   ```

   The bootstrap script creates a tenant ID and prints it. The admin can sign in at `/login`, then connect the store from Settings. Admins can add analyst and viewer accounts through the tenant-scoped `/team/users` API. Only admins can connect stores or manage team access; all analytics queries are scoped to the authenticated user's tenant.

## Shopify app setup

Replace the client ID and application URL in `shopify.app.toml`, configure the same app credentials in `backend/.env` and `.env.local`, and deploy the app configuration. The app uses Shopify App Bridge ID tokens and the embedded token-exchange grant. It requests expiring offline access tokens and rotates the encrypted refresh-token pair before expiry.

The configured scopes are `read_reports`, `read_orders`, `read_products`, `read_inventory`, and `read_customers`. ShopifyQL analytics require `read_reports` and Shopify's required protected-customer-data approval for the relevant reports. Request that approval and install the app with the required scopes before expecting live reports. Set `CORS_ORIGINS` to the deployed dashboard origin.

## API

- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `POST /shopify/token-exchange`, `GET /store/connection`
- `GET /analytics/overview?days=7|30|90`, `GET /analytics/products`, `GET /analytics/orders`, `GET /analytics/customers`, `GET /analytics/forecast`, `GET /analytics/alerts`
- `GET /team/users`, `POST /team/users` (admin only)

Logout increments the account's token version, invalidating its outstanding JWT sessions. The UI uses sample data when no authenticated Shopify connection is available.
