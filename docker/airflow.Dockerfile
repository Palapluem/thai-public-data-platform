FROM apache/airflow:2.10.5-python3.12

USER root

COPY pyproject.toml README.md /tmp/thai-public-data-platform/
COPY src /tmp/thai-public-data-platform/src

RUN python -m pip install --no-cache-dir /tmp/thai-public-data-platform

USER airflow
