FROM ubuntu:20.04

RUN apt-get update && \
    apt-get install -y tmate openssh-server && \
    apt-get clean

CMD ["bash"]
