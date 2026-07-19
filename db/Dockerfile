# PostGIS image does not ship pgvector. Install it so 00_extensions.sql can
# CREATE EXTENSION vector on first boot.
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
