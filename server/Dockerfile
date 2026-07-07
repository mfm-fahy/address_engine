FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev python3-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --verbose torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --verbose -r requirements.txt

RUN python -c "from transformers import pipeline; pipeline('summarization', model='Falconsai/text_summarization', tokenizer='Falconsai/text_summarization')"

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN addgroup --system --gid 1001 app && adduser --system --uid 1001 app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/huggingface /home/app/.cache/huggingface
COPY . .
RUN chown -R app:app /app /home/app/.cache/huggingface
USER app
ENV HF_HOME=/home/app/.cache/huggingface
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
