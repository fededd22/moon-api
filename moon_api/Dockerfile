FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

# مستخدم الصندوق الرملي: يُشغَّل به كود العملاء، ولا يملك أي صلاحية على /app/data
RUN useradd --no-create-home --shell /usr/sbin/nologin --uid 10001 sandbox

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY start.sh .
RUN chmod +x start.sh && mkdir -p /app/data && chmod 700 /app/data

EXPOSE 8000
# MODE = api | bot | all
ENV MODE=api
CMD ["./start.sh"]
