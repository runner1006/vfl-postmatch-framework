# Reine Standardbibliothek - deshalb genuegt das schlanke Basisimage ohne
# jeden Installationsschritt.
FROM python:3.12-slim

WORKDIR /app
COPY . /app/scoutleague

# Die Datenbank liegt auf einem Volume, nicht im Image: ohne Mount ist die
# Liga nach jedem Neustart leer.
ENV SCOUTLEAGUE_DB=/data/scoutleague.db \
    PORT=8080
VOLUME ["/data"]
EXPOSE 8080

CMD ["python3", "/app/scoutleague/serve.py"]
