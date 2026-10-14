# Home AI System — React Console

**Version:** 2.0 React redesign · **UI language:** English · **Target:** Ubuntu Mini PC or Mac mini, Docker Compose.

This project adds a home intelligence decision layer above existing **Fox ESS / FoxCloud**, **Octopus Energy**, and **UniFi Protect** applications. It does not duplicate full inverter telemetry dashboards, NVR live views, or native Protect recordings.

## What changed in v2

- Replaced the legacy static HTML/JavaScript UI with **React 19 + TypeScript + Vite**.
- Introduced a single **responsive light-mode visual system**, influenced by UniFi's restrained blue/white management console style, without copying UniFi branding or proprietary assets.
- Desktop: permanent sidebar + operational workspace + slim context rail. Tablet: context rail becomes secondary content. Phone: compact header, stacked cards, and five bottom navigation items.
- Pages: **Overview, Energy, Security, Assistant, Automation, History, Settings**.
- Real FastAPI integration for health, FoxCloud telemetry, stored plans, 48h simulation, event history and conversation.
- Clearly labeled preview/demo states. UI never claims that an integration is connected just because the API container is running.
- UI controls **cannot write Fox ESS schedules**; they only generate/store optimiser simulations.

## Quick start with Docker (recommended)

The build machine requires network access to install the React/npm packages when building the image for the first time. On your Mini PC:

```bash
unzip Home_AI_System_React_Unifi_UI.zip
cd Home_AI_System
cp .env.example .env
docker compose up --build -d
```

Open `http://127.0.0.1:5173` locally. To open it from another device over a trusted LAN/VPN, change `DASHBOARD_BIND_IP` in `.env` to the Mini PC's own LAN IP. Do **not** publish it directly to the internet; there is no production login or HTTPS terminator included.

Stop with `docker compose down`. Data stays in the `appdata` Docker volume.

## Local React frontend development

```bash
cd frontend
npm install
npm run dev
```

In another terminal, run the FastAPI backend on port 8000 (via Docker or directly). Vite proxies `/api` to `http://127.0.0.1:8000`.

Build the static React UI with:

```bash
npm run build
```

Vite outputs `frontend/dist/`. Docker's multistage Dockerfile builds the UI using Node 22 and serves it through Nginx, with a reverse proxy to `api:8000`.

## Functionality and its limits

| Area | Included now | Not yet included |
| --- | --- | --- |
| UI | Responsive React/TypeScript design and navigation | Authentication / remote HTTPS |
| Energy | Read adapter, simulated 48h numerical optimisation and stored history | Verified KH7 Scheduler writes, tariff-grade forecasts |
| Security | Authenticated Protect webhooks and event history | Automatic snapshot retrieval, cloud vision pipeline, push alerts |
| AI | Optional OpenAI Agent + private MCP tools | Offline/local LLM and full autonomous device operation |
| Storage | Single-node SQLite on Docker volume | Clustered multi-node persistence |

### Essential safety conditions

- **Real battery schedule writes are permanently disabled in this starter**, independently of the frontend. A generated optimisation is **not** the FoxCloud Schedule V3 payload.
- The UI's “Generate simulation” button only calls the optimiser and records its forecast. It never changes equipment operation.
- Do not assume demo prices or illustrative security events are real detections. If `MOCK_MODE=true` the app shows a prominent demo banner.
- Protect remains responsible for native camera alerts and recording; the starter is **not** a substitute for a monitored alarm system.
- Before sending camera images to an AI vendor, add consent, opt-in, privacy/retention controls, rate limiting, and a vetted snapshot retrieval adapter.
- Keep secrets **only** in `.env` on the server. Do not paste credentials into the web interface.

## API integration

The React UI calls these existing FastAPI endpoints:

```
GET  /api/health
GET  /api/system/config
GET  /api/energy/status
GET  /api/energy/plan
POST /api/energy/plan              # Simulation only
GET  /api/energy/history
GET  /api/security/events
POST /api/chat                     # Requires configured OpenAI + MCP
```

Your Fox ESS / Octopus / Protect integration settings remain in `.env.example`. Instructions for Protect webhook configuration, optimiser mathematics, and MCP servers are in `docs/ARCHITECTURE.md`.

## Tests / verification

The backend tests can be run with:

```bash
cd backend
pytest -q
```

The React TSX source has been syntax-transpiled and smoke-rendered in an offline browser harness at multiple widths (320–1600px) without horizontal overflow. The harness is not a substitute for a production React build. A production `npm run build` could not be executed there because npm registry access was unavailable. Run that command on the target Mini PC to verify the final dependency installation, type check and bundle. We do not present unverified preview screenshots as product screenshots.

## Original architecture preserved

`backend/` contains the tested Python services, scheduler, mathematical optimiser, Protect event processing and MCP adapters from the earlier project. `frontend/` is now a true React source project. `docker-compose.yml` continues to deploy them together.
