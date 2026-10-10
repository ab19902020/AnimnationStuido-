# The Animation Studio as a web app on a server (see DEPLOY.md). Speech models are fetched on first use into
# models/, which tools/serve.sh keeps on the persistent disk with everything else the studio makes.
ARG BASE=python:3.13-slim
FROM ${BASE}
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg libegl1 libgl1 libfontconfig1 libsndfile1 poppler-utils curl bzip2 unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 STUDIO_DATA=/data PORT=8000
EXPOSE 8000
CMD ["bash", "tools/serve.sh"]
