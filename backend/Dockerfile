FROM python:3.11-alpine

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/ fastapi uvicorn httpx pydantic
WORKDIR /app
COPY app.py .
EXPOSE 5000

HEALTHCHECK CMD python3 -c "import http.client; c=http.client.HTTPConnection(\"localhost\",5000,timeout=5); c.request(\"GET\",\"/health\"); r=c.getresponse(); exit(0 if r.status==200 else 1)" || exit 1

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
