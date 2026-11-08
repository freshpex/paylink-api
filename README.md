# Paylink API

FastAPI backend for a multi-company, branded **manual payment confirmation** platform. The React application lives in the separate `paylink-web` repository.

Admins publish payment instructions (bank transfer, PayPal email, crypto wallet/network, or any named method). Customers transfer funds externally and submit a report. An authorized company owner checks their own account and confirms or rejects the report. Confirmation atomically saves a receipt snapshot, audit entry, and durable Mailjet outbox item.

**Paylink does not initiate transfers or independently verify funds.** An Apple Pay or PayPal label is an instruction label, not a gateway integration. Receipts record the company's confirmation.

## Run locally

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env
# Set JWT_SECRET to a unique random value (at least 32 characters).
# Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'
uv sync --frozen --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Run the frontend on `http://localhost:5173`. Development uses SQLite; production uses PostgreSQL via `postgresql+psycopg://...`. `COOKIE_SECURE=false` is for local HTTP only. Interactive API documentation: `http://localhost:8000/docs`.

### Neon PostgreSQL

Set `DATABASE_URL` to the pooled Neon connection string and `DATABASE_URL_UNPOOLED` to the direct (unpooled) connection string. Standard `postgresql://` and `postgres://` URLs are accepted and use the installed Psycopg 3 driver. Keep Neon's `sslmode` and `channel_binding` query parameters. The API uses `DATABASE_URL`; Alembic uses `DATABASE_URL_UNPOOLED` when present and otherwise falls back to `DATABASE_URL`. SQLAlchemy does not retain a second connection pool on top of Neon, and connection attempts have a 10-second timeout.

Run `uv run --frozen alembic upgrade head` once as a release step before serving the application. Do not run migrations on every request or function startup. Tests always use an isolated in-memory database, even when Neon URLs are injected into the environment.

### Vercel frontend and API

Vercel detects the FastAPI entrypoint at `app/main.py`; import this repository as a separate FastAPI project with its root set to this checkout. Set the pooled and unpooled Neon variables, a strong `JWT_SECRET`, `FRONTEND_URL=https://paylink-web-rho.vercel.app` (no trailing slash), and `COOKIE_SECURE=true` in that API project's environment settings.

The companion web repository proxies `/api` to `https://paylink-api-sepia.vercel.app`. That API domain must point to the deployed FastAPI project. The different hostname `https://paylink-api.vercel.app` returns Vercel `NOT_FOUND`; adding CORS headers cannot make a nonexistent deployment serve the API. If the API domain changes, update the web repository's proxy destination and redeploy the frontend. The proxy preserves same-origin browser requests and the HttpOnly, SameSite=Lax session cookie. Keep the exact frontend origin check enabled.

A successful deployment returns `200` with `{"status":"ok"}` from `/health`; an unauthenticated `/api/v1/auth/me` returns `401` with the frontend origin allowed. Readiness checks should not register users or send emails against production.

Every browser mutation requires the exact configured `FRONTEND_URL` as its `Origin` header. Set this header when testing mutations through API docs or another client. Session cookies are HttpOnly, SameSite=Lax, eight-hour JWTs. Deploy frontend and API on the same site, ideally behind a reverse proxy with `/api` forwarded to the API. Cross-site deployments are not supported by this cookie policy.

## Mailjet and Cloudinary

Set Mailjet API key, secret, and a verified `MAIL_FROM` sender in server environment variables, then run:

```sh
uv run python -m app.worker
```

Only confirmed payments enqueue receipt emails. Emails include the customer's receipt download page. The worker retries failed delivery every 30 seconds up to 12 attempts. Inspect and reset exhausted rows after correcting delivery problems. Sending is at least once: a crash after provider acceptance but before commit can duplicate an email. PostgreSQL workers use `SKIP LOCKED`; use only one worker with SQLite.

Set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` to enable signed direct uploads of company logos, page images, and videos. The frontend caps uploads at 20 MB. Configure Cloudinary account-side size, format, and delivery restrictions as well; browser limits alone are not enforcement. Media uploads are public brand assets; do not upload identity documents or transfer evidence.

## Structure

```text
app/api/          Authentication, company, link, review, and public route modules
app/core/         Validated configuration, sessions, tenant authorization, database, rate limiter
app/models/       SQLAlchemy entities and database constraints
app/schemas/      Pydantic input contracts
app/worker.py     Transactional receipt outbox and Mailjet adapter
alembic/          Versioned database schema migrations
tests/           Tenant isolation, state transitions, media signing, outbox retry tests
```

Each company has its own memberships, branding, links, payment reports, and audit history. Owner membership is required for changes and payment review. Registration creates an owner and their first company; an owner can create more companies. Team invitation management is not included.

Money is stored as integer minor units with a fixed amount on each link. Supported two-decimal currencies are USD, NGN, GBP, EUR, SAR, CNY, AED, AUD, CAD, CHF, HKD, INR, KES, ZAR, SGD, NZD, GHS, EGP, TRY, MYR, PKR, BDT, BRL, MXN, and THB. Crypto payment instructions can specify the wallet, network, and exchange instructions; accounting amounts remain denominated in the selected fiat currency.

Public links omit optional private recipient fields. Public payment and receipt IDs are random UUID capabilities: anyone possessing a receipt URL can see its payer name and email. Treat URLs as private, disable access logging of full receipt paths at your edge, and avoid third-party analytics on these pages. Confirmed receipts retain their original company/branding snapshot when company settings change. Receipt PDFs/images are generated by the frontend and do not require browser printing.

## Validation

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

The workflow includes automated checks. Integration tests mock Mailjet and test Cloudinary signing without contacting those services. The companion frontend has a browser smoke test for the full manual-payment journey.

## Deployment and operations

1. Provision PostgreSQL, supply environment variables through your secret manager, and enforce HTTPS with `COOKIE_SECURE=true`.
2. Run `alembic upgrade head` once as a release step, then start the API and receipt worker separately. The Docker image runs as a non-root user.
3. Reverse-proxy `/api` to port 8000, keep the frontend origin exact, and set edge body-size, timeout, and rate limits. `/health` checks database reachability.
4. Back up PostgreSQL and test restores. Preserve receipt snapshots and audit history according to your retention policy. Restrict database access and encrypt backups.
5. Monitor API errors, failed logins, pending reviews, worker heartbeat, and unsent/exhausted outbox rows. Audit history is available at `/api/v1/companies/{id}/audit` to company owners.

This is a tested application foundation, not a claim of security certification or regulatory compliance. Before a high-assurance launch, add MFA/SSO, verified email and password recovery, session revocation, an external shared rate-limit store, team invitation workflows, receipt revocation/correction policy, monitoring, and independent security review. Current list endpoints return the latest 200 records; analytics are explicitly limited to those rows. Review pagination/reporting requirements before large-scale use.

No service credentials are committed. Never put backend secrets in Vite environment variables.
