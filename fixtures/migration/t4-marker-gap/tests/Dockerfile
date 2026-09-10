FROM python:3.12-slim-bookworm@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

RUN python3 -m pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2

COPY . /tests/

RUN mkdir -p /app

CMD ["sleep", "infinity"]
