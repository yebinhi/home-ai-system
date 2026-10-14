FROM python:3.12-slim
WORKDIR /opt/home-ai
COPY pyproject.toml .
COPY homeai ./homeai
RUN pip install --no-cache-dir .
RUN useradd -r -u 10001 homeai && mkdir -p /data && chown -R homeai:homeai /data
USER homeai
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "homeai.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
