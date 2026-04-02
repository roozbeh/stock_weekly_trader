FROM python:3.12-slim

WORKDIR /app

RUN mkdir -p /app/reports

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

ENV BUDGET=10000
ENV TARGET_PCT=5.0
ENV STOP_PCT=3.0
ENV SCHEDULE_TIME_UTC=14:35

VOLUME ["/app/reports"]

CMD ["python", "scheduler.py"]
