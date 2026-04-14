FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    iproute2 iptables kmod net-tools curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/netemu

COPY backend/requirements.txt /opt/netemu/backend/requirements.txt
RUN python3 -m venv /opt/netemu/venv \
    && /opt/netemu/venv/bin/pip install --no-cache-dir -r /opt/netemu/backend/requirements.txt

COPY backend /opt/netemu/backend
COPY frontend /opt/netemu/frontend

EXPOSE 8080

CMD ["sh", "-c", "modprobe sch_netem 2>/dev/null || true; modprobe ifb 2>/dev/null || true; cd /opt/netemu/backend && /opt/netemu/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8080 --log-level info"]
