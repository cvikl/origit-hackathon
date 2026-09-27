# Origit Console: FastAPI + the origit core (vendored submodule) + git. Node 24 + Bob Shell are installed best-effort
# so the reviewer/drafter can run when BOB_API_KEY is set; if the installer fails the image still works (cached evidence only).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates bash && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/* || echo "node install failed"
RUN (curl -fsSL https://bob.ibm.com/download/bobshell.sh -o /tmp/bobshell.sh && timeout 300 bash /tmp/bobshell.sh --pm npm </dev/null && command -v bob && bob --version) || echo "Bob Shell not installed at build time"
WORKDIR /srv
COPY vendor/origit/origit ./vendor/origit/origit
RUN pip install --no-cache-dir ./vendor/origit/origit
COPY pyproject.toml ./
COPY app ./app
COPY prompts ./prompts
COPY seed ./seed
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" jinja2 python-multipart markdown
ENV ORIGIT_DATA_DIR=/data PROMPTS_DIR=/srv/prompts SEED_DIR=/srv/seed PYTHONUNBUFFERED=1
RUN git config --global --add safe.directory '*' && git config --global user.name origit-console && git config --global user.email console@origit.uk
EXPOSE 8787
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787", "--proxy-headers", "--forwarded-allow-ips", "*"]
