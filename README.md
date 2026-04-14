# NetEmu Rewrite

A clean rewrite of the original NetEmu design: FastAPI backend, static SPA frontend, Linux `tc` and `iptables` orchestration, persistent JSON rule storage, real-time WebSocket stats, and profile-driven rule editing.

## What changed from the original

- Removed `shell=True` command execution. All Linux tooling is invoked through argument lists.
- Enforced one persisted rule per interface so stored state matches actual `tc` state.
- Fixed variation so it preserves the original direction (`egress`, `ingress`, `both`).
- Fixed ingress shaping design so `ingress` no longer accidentally applies root qdisc on the physical interface.
- Made CORS configurable and safe by default.
- Reworked the frontend WebSocket lifecycle to avoid runaway reconnect and ping timers.

## Project layout

```text
netemu/
  backend/
    api/
    core/
    data/
    profiles/
    main.py
    requirements.txt
  frontend/
    static/css/main.css
    static/js/api.js
    static/js/ui.js
    static/js/app.js
    templates/index.html
  Dockerfile
  docker-compose.yml
  install.sh
  netemu.service
  README.md
```

## Run locally

```bash
cd backend
pip install -r requirements.txt
sudo python main.py
```

Open:

- UI: `http://<host>:8080`
- API docs: `http://<host>:8080/docs`
- Health: `http://<host>:8080/health`

## Environment variables

- `NETEMU_HOST` default `0.0.0.0`
- `NETEMU_PORT` default `8080`
- `NETEMU_DATA_DIR` default `backend/data`
- `NETEMU_MONITOR_INTERVAL_S` default `2.0`
- `NETEMU_ALLOWED_ORIGINS` default `http://localhost:8080,http://127.0.0.1:8080`

## Notes

This project still assumes a Linux runtime with `iproute2`, `iptables`, and root or equivalent `CAP_NET_ADMIN` privileges. Windows can edit and validate the source, but it cannot execute the actual traffic-control path.
