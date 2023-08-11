FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qy \
 && apt-get upgrade -qy \
 && apt-get install -y \
    bridge-utils \
    iproute2 \
    python3-ipy \
    socat \
    qemu-kvm \
 && rm -rf /var/lib/apt/lists/*

#COPY vjunosswitch /vjunosswitch
ARG IMAGE
COPY $IMAGE* /

COPY *.py /
COPY *.sh /
COPY *.conf /
COPY config.img /

# create config disk to mount
# run this before then copy config.img to container?
#RUN ./make-config.sh juniper.conf config.img

#CMD ["/make-config.sh", "juniper.conf", "config.img"]

EXPOSE 22 161/udp 830 5000 10000-10099 57400
HEALTHCHECK CMD ["/healthcheck.py"]
ENTRYPOINT ["/launch.py"]
