FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y tmate openssh-client && \
    apt-get clean

CMD ["tmate", "-F"]
