FROM alpine:3.20

RUN apk add --no-cache \
    python3 \
    py3-fastapi \
    py3-uvicorn \
    py3-httpx \
    py3-pydantic \
    && rm -rf /var/cache/apk/*

WORKDIR /app
COPY app.py .

EXPOSE 5000

HEALTHCHECK CMD python3 -c "import http.client; c=http.client.HTTPConnection(\"localhost\",5000,timeout=5); c.request(\"GET\",\"/health\"); r=c.getresponse(); exit(0 if r.status==200 else 1)" || exit 1

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
