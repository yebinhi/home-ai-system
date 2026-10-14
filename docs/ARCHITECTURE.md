# Home AI System Architecture (React UI 2.0)

## System diagram

```text
Browser: React 19 + TypeScript (desktop / tablet / mobile)
      |
      v
Nginx HTTPS-ready reverse-proxy target (currently LAN/VPN HTTP only)
      |
      +--> /api/* --> FastAPI (Python)
                       |
                       +--> Daily scheduler (22:00 Europe/London)
                       |        |
                       |        +--> 48-hour / half-hour energy optimiser (SciPy / HiGHS MILP)
                       |        +--> SQLite simulation history
                       |
                       +--> Authenticated UniFi Protect webhooks --> event records
                       |
                       +--> Read-only FoxCloud adapter / Octopus tariff adapter
                       |
                       +--> Home Agent (LangChain/LangGraph)
                              |
                              +--> private MCP tools (Fox ESS, Octopus, UniFi, optimiser)
```

## Separation of responsibilities

- **UI:** Explainable forecasts, decisions, exception inbox, history, and AI questions.
- **Energy scheduler:** Once a day, generate a new 48h plan; no device writes.
- **Optimiser:** Numerical economic optimisation with battery SOC constraints, import/export costs, charge/discharge exclusivity and degradation approximation. For the user's 8p overnight versus higher solar export price, it can consider cheap overnight charging instead of automatically assigning all PV to storage. Values are scenario-dependent.
- **Security:** UniFi Protect generates detections and records video. A token-authenticated webhook sends event metadata to the backend. AI still-image analysis is optional and not automatically connected in this starter.
- **MCP:** Tools expose device and analytical operations to LangGraph; no direct safety-critical writes from LLM outputs.

## Frontend tree

```text
frontend/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  Dockerfile
  nginx.conf
  public/
    favicon.svg
  src/
    main.tsx
    App.tsx                     # responsive pages + state
    api.ts                      # typed API calls
    types.ts                    # contracts
    icons.tsx                   # consistent SVG icon set
    styles.css                  # design tokens + breakpoints
```

## Responsive behavior

- **Desktop (`>1100px`):** left sidebar, main decision panel, right assistant/system/history rail.
- **Small desktop/tablet (`761–1100px`):** full main content with stacked contextual rail.
- **Phone (`<=760px`):** left sidebar hidden; sticky topbar, condensed summary cards and bottom tab navigation; Automation/History/Settings available through More.
- **Very narrow phones (`<=410px`):** tighter typography and single-column controls.

## Palette and visual identity

This UI is *inspired by* UniFi's clarity, light surfaces and blue interactive elements. It is not an official UniFi product or a pixel-perfect reproduction.

- Main blue: `#006FFF`
- Page surface: `#F7F9FC`
- Card surface: `#FFFFFF`
- Borders: `#E7ECF2`
- Text: `#19283F`
- Secondary text: `#7C8B9D`
- Online green: `#00A76F`

## Production hardening checklist

1. Deploy authenticated reverse proxy with TLS and LAN/VPN restriction.
2. Verify FoxCloud KH7 telemetry fields and outbound API usage.
3. Confirm the actual Octopus import/export contractual rates and DNO limit.
4. Add battery write approval and independent safety checks before enabling scheduling.
5. Validate Protect event schemas; use a dedicated event queue for snapshot processing.
6. Obtain consent before uploading security snapshots to an AI service, with retention limits.
7. Keep operating-system updates, backups, monitoring and credential rotation in place.
