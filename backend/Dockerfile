# クラウドで動かすAPIのコンテナイメージ。データの投入（`python -m app.seed`）にも、同じものを使う。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_SSL_ROOT_CERT=/app/rds-ca.pem

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --no-create-home app

# RDSのサーバー証明書を検証するための、AWSの認証局の証明書。
ADD --chmod=444 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /app/rds-ca.pem

COPY app ./app

# 管理者ではない利用者で実行する。
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
