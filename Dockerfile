# Dockerfile - ubuntu + tmate (keeps container alive so bot can exec tmate)
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      tmate openssh-client ca-certificates curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Keep container alive; tmate session will be created by bot via `docker exec`
CMD ["tail", "-f", "/dev/null"]
