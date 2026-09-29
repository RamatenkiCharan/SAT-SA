# SAT-SA Render Deployment Guide

This guide details how to deploy the Supervisory Analytics Tool for SOC Assessment (SAT-SA) to Render using the official Render Blueprint configuration.

## 1. Architecture

The deployed application follows a 3-tier architecture utilizing Render's free tier:

- **Frontend (Static Site):** React SPA built with Vite. It builds via `npm run build` and serves static files globally from the `dist` directory via a CDN.
- **Backend (Web Service):** FastAPI Python backend handling analytics, authorization, and dataset processing. It binds to Render's dynamic `$PORT` and is built using native Python environments (`pip install -r requirements.txt`).
- **Database (PostgreSQL):** Render-managed durable PostgreSQL instance. Migrations are executed securely and automatically by the backend upon connection.

## 2. Render Services

When deployed, the Render Blueprint will automatically provision the following:
1. `satsa-db`: The PostgreSQL Database.
2. `satsa-backend`: The FastAPI web service.
3. `satsa-frontend`: The React/Vite static site.

## 3. Required Environment Variables

The `render.yaml` blueprint manages most environment variables automatically. However, you can control the application using the following keys:

- `DATABASE_URL`: Connection string (provided automatically by Render).
- `SAT_SECRET_KEY`: Used for JWT authentication (generated automatically by Render Blueprint).
- `SAT_ENV`: Set to `production`.
- `SAT_ALLOWED_ORIGINS`: Set to your frontend domain (e.g., `https://satsa-frontend.onrender.com`) to enforce CORS.
- `VITE_API_URL`: Set in the frontend static site to point to your backend API URL (e.g., `https://satsa-backend.onrender.com/api`).
- `SAT_PERSISTENCE_MODE`: Set to `postgres`.

*If deploying for demonstration/hackathon purposes, you may optionally set:*
- `SAT_SEED_DEMO_DATA=true` (Pre-loads synthetic dataset)
- `SAT_SEED_DEMO_USERS=true` (Allows setting up demo accounts using the bootstrap passwords)
- `SAT_BOOTSTRAP_ADMIN_PASSWORD` (Your desired demo admin password)

> **Important Security Rule:** See `.env.example` for the full list of configuration keys. Never commit real credentials to your repository.

## 4. PostgreSQL Connection & Migrations

- The backend determines its connection via the `DATABASE_URL`. It automatically rewrites the legacy `postgres://` prefix provided by Render to the required `postgresql+psycopg2://` driver prefix.
- **Migrations:** SAT-SA handles database migrations autonomously. Upon server startup, the `PostgresRepository` connects to the database, compares the `_schema_migrations` table, and applies any pending SQL files located in `database/migrations/`. You do not need to run a manual migration command.

## 5. Connecting Frontend to Backend

The frontend builds using the `VITE_API_URL` environment variable. This ensures the compiled React application explicitly routes all API calls (e.g., `/api/auth/login`) to the public Render backend URL instead of localhost, ensuring a decoupled architecture.

## 6. How to Redeploy

Since the project is connected via GitHub:
1. Push your changes to the `main` branch.
2. Render will automatically detect the changes and trigger new builds for both the Web Service and Static Site.

## 7. Inspecting Logs & Testing

- Access logs directly through the **Render Dashboard**.
- Each service (Backend, Frontend) has a "Logs" tab that shows build progress, startup information, and live request logs.
- To test deployment, navigate to your public Static Site URL (`https://satsa-frontend.onrender.com`), verify that the login page loads, and successfully authenticate using your bootstrap credentials.

## 8. Render Free-Tier Limitations

Keep the following in mind when running SAT-SA on Render's free tier:
- **Cold Starts:** The FastAPI backend will go to sleep after 15 minutes of inactivity. The first request after a sleep period may take up to 50 seconds to respond. The frontend will gracefully show loading indicators during this time.
- **Compute Limits:** Memory and CPU are strictly limited. Ensure uploaded datasets for analysis do not exceed reasonable hackathon sizes, or the instance may OOM (Out Of Memory) crash.

## 9. Security Considerations

- **CORS:** Only the configured frontend origin is allowed. Do not use wildcard `*` origins in production.
- **Authentication:** All authentication logic, JWT security, and Role-Based Access Control (RBAC) remain strictly enforced. 
- **Database Exposure:** The PostgreSQL database is completely isolated; it does not need to be exposed externally (0.0.0.0), as the backend connects via Render's internal network.
