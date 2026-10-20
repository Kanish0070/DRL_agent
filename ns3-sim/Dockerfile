# ==============================================================================
# Dockerfile for NS-3.41 AoI Scheduler evaluation environment
# Ensures turnkey cross-platform consistency across Windows, Linux, and macOS
# ==============================================================================
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV NS3_VERSION=3.41
ENV NS3_HOME=/opt/ns3
ENV NS3_DIR=${NS3_HOME}/ns-allinone-${NS3_VERSION}/ns-${NS3_VERSION}

# Install core build and testing dependencies
RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build g++ ccache git curl \
    python3 python3-pip python3-dev python3-setuptools \
    python3-numpy python3-scipy python3-matplotlib python3-yaml \
    python3-pytest python3-flask \
    qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools \
    libsqlite3-dev libxml2-dev libxml2-utils \
    && rm -rf /var/lib/apt/lists/*

# Download and compile NS-3
WORKDIR ${NS3_HOME}
RUN curl -fSL -o ns-allinone-${NS3_VERSION}.tar.bz2 https://www.nsnam.org/release/ns-allinone-${NS3_VERSION}.tar.bz2 \
    && tar xjf ns-allinone-${NS3_VERSION}.tar.bz2 \
    && rm ns-allinone-${NS3_VERSION}.tar.bz2 \
    && cd ${NS3_DIR} \
    && ./ns3 configure --enable-examples --enable-tests \
    && ./ns3 build -j$(nproc)

# Setup workspace
WORKDIR /workspace/DRL_agent

# Install entrypoint script
COPY ns3-sim/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["test"]
