FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

COPY main.py pyproject.toml /app/
COPY src /app/src
COPY copilot /app/copilot
COPY scripts /app/scripts

ENTRYPOINT ["python", "main.py"]
CMD ["doctor"]
