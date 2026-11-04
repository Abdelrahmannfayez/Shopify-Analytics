# Northstar Shopify Analytics

A responsive, bilingual (English / Arabic) Shopify analytics dashboard built with Next.js App Router, TypeScript, Tailwind CSS, ECharts and lucide-react. The UI currently uses representative sample data. The FastAPI service provides a tenant-scoped JWT auth and MySQL integration starter.

## Run the dashboard

```bash
npm install
npm run dev
```

## Run the API

1. Create the `master` database and tables with `backend/schema.sql`.
2. Copy `backend/.env.example` to `backend/.env`; set a strong random `JWT_SECRET` and your MySQL URL.
3. Install `backend/requirements.txt`, then run `uvicorn main:app --reload` from `backend/`.

The first admin account must be provisioned by a trusted operator with a bcrypt password hash. The Shopify access token column is intended to contain application encrypted data; add a managed encryption key and encrypt/decrypt service before storing live credentials. Analytics endpoints are placeholders until Shopify Admin API aggregation and tenant data access are connected.
