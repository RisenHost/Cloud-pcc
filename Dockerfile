FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y tmate openssh-client curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Keep container alive; bot will exec tmate inside.
CMD ["tail", "-f", "/dev/null"]
