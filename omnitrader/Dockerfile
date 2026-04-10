FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install PyPI dependencies
COPY pyproject.toml ./
RUN uv sync --no-dev

# Install E.SUN SDK wheels (Linux build)
COPY module/linux/ ./module/linux/
RUN uv pip install \
    module/linux/esun_trade-2.2.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl \
    module/linux/esun_marketdata-2.2.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

COPY src/ ./src/

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uv", "run", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
