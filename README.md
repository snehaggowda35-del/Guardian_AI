# Guardian AI

Guardian AI is a privacy-aware digital-safety MVP for parent-authorized browser monitoring. It detects potentially concerning searches or web-chat text, evaluates a short relevant context window, selectively discloses evidence, and lets the parent make the final decision.

> This prototype is not a medical, emergency, or surveillance product. It does not replace professional support or emergency services. Use only with informed authorization and in compliance with local law.

## Included

- FastAPI API, dashboard and SQLite persistence (PostgreSQL-ready ORM configuration)
- Deterministic safety classifier and multi-stage investigation workflow
- Link-code device registration and JWT parent authentication
- Alert audit trail, acknowledgement, privacy minimization and configurable retention
- Manifest V3 Chrome extension for Google searches and an opt-in generic chat selector
- Automated backend tests and seeded demo account

## Run locally

```powershell
cd "C:\Users\Admin\OneDrive\Desktop\Guardian_AI"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
if (!(Test-Path .\backend\.env)) { Copy-Item .\backend\.env.example .\backend\.env }
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\backend --host 127.0.0.1 --port 8000 --reload
```

Using the venv's executables directly avoids PowerShell execution-policy errors and
ensures the API and dashboard use the same project database. If an older server is
already running, stop it with `Ctrl+C` before starting this command.

Open http://127.0.0.1:8000. The development account is `parent@example.com` / `ChangeMe123!`; change it before any real use.

### Optional managed AI analysis

The project is configured for `AI_PROVIDER=openai` so the server can use broader multilingual semantic analysis. Put the provider key in the uncommitted `backend/.env` file:

```text
AI_PROVIDER=openai
OPENAI_API_KEY=your-server-side-key
OPENAI_MODEL=gpt-4o-mini
```

If the key is blank or the provider is unavailable, the auditable local rules classifier is used as a fallback. The key stays on the server; never put it in the browser extension. Only the trigger and the capped safety-relevant context are sent when this mode is enabled. The model is advisory, its response is constrained to JSON, and local deterministic thresholds still decide whether a parent alert is created. Review your provider's data controls, regional processing, retention, and applicable child-safety/privacy obligations before enabling it for real users. Check `/health` to see `semantic_ai_enabled`.

## Public deployment outline

1. Provision a managed PostgreSQL database and a server/container with a public HTTPS domain.
2. Set `DATABASE_URL`, a long random `JWT_SECRET`, `ENVIRONMENT=production`, and the exact HTTPS dashboard origin in `backend/.env`. Do not commit that file.
3. Build and run the container with `docker compose up --build` for a controlled staging environment, or deploy the `backend/Dockerfile` to your cloud provider. Put TLS at a managed load balancer/reverse proxy and restrict database access to the API network.
4. Create a privacy-policy URL (the included `/privacy` page is a starting point), configure account email verification/password recovery, backups, retention deletion, rate limits, monitoring, and an incident-response contact before inviting real families.
5. Zip only the `extension/` directory and publish it through the Chrome Web Store Developer Dashboard. Complete the Store Listing, Privacy, Distribution, and Test instructions sections and submit it for review. The store requires a declared single purpose, user-data disclosure/consent, secure transmission, and minimum permissions.

The repository now supports self-service parent registration and account-owned devices/alerts. Email verification, password recovery, managed push/email notifications, a production multilingual model, and legal/compliance review remain required before a public launch.

Load `extension/` as an unpacked extension in `chrome://extensions`, open its popup, set the API URL, sign in, create a device code in the dashboard, then link the extension with that code.

## Safety and privacy choices

- Normal events are not stored. Only safety-relevant events can be retained.
- Context is capped at three relevant events from the last 24 hours.
- Only the trigger and relevant context are disclosed in an alert.
- The dashboard clearly labels results as automated signals, not diagnoses.
- The extension has no broad host permissions; Google is enabled by default and any additional chat site must be deliberately entered by the parent.

## Production readiness (important)

The included `rules-v2` analyzer is a transparent development baseline, not a complete language-understanding system. It covers common English direct/indirect patterns and conservative negation/benign-context checks so the end-to-end loop is testable. It must not be advertised as diagnosing risk or understanding every language.

Before deployment, replace or augment it with a properly evaluated multilingual text-classification service and keep deterministic policy gates around it. Establish a labeled, lawfully sourced evaluation set (by language, age-appropriate context, and risk category), measure precision/recall and false-negative rates, run red-team tests for evasion and prompt injection, encrypt data in transit and at rest, add tenant isolation and key rotation, define deletion/retention controls, rate-limit ingestion, and provide an on-call human review/escalation process. Never use model output as the sole basis for an emergency intervention.

## Project layout

`backend/` contains the API and workflow, `extension/` contains the browser extension, and `tests/` covers classifier and API flows.
