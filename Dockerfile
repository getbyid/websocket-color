FROM python:3.11-slim AS compile-image

RUN python3 -m venv /opt/venv

# Make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

RUN python3 -m pip install --upgrade pip; pip3 install websockets redis[hiredis]

FROM python:3.11-slim
COPY --from=compile-image /opt/venv /opt/venv

# Make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /api
COPY server.py .
CMD ["python3", "server.py"]
