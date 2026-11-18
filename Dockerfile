# Airflow image for the pipeline (based on the setup in branch "pimmy").
FROM apache/airflow:2.10.5-python3.11

# Java is needed by PySpark (brief requires Spark for cleaning/joining).
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
 && rm -rf /var/lib/apt/lists/* \
 && ln -s "$(dirname "$(dirname "$(readlink -f "$(which java)")")")" /usr/lib/jvm/java-17
# Same path on Intel/AMD (amd64) and ARM (arm64) machines.
ENV JAVA_HOME=/usr/lib/jvm/java-17

USER airflow
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
# The constraints file pins versions Airflow 2.10.5 is tested with, so pip cannot break Airflow.
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.11.txt"

ENV PYTHONPATH=/opt/airflow/src \
    PROJECT_ROOT=/opt/airflow
