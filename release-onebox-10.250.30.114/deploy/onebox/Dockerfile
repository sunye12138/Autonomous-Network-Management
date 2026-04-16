FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"

WORKDIR /app

RUN apt-get update     && apt-get install -y --no-install-recommends bash ca-certificates curl iputils-ping     && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt

COPY backend/app /app/app
COPY backend/host_agent.py /app/backend/host_agent.py
COPY frontend /app/frontend
COPY deploy/onebox/start-onebox.sh /app/start-onebox.sh

RUN chmod +x /app/start-onebox.sh

EXPOSE 8000 14173

CMD ["/app/start-onebox.sh"]
