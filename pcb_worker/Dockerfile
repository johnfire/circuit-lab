FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
RUN apt-get update && apt-get install -y --no-install-recommends kicad=9.0.2+dfsg-1 kicad-footprints=9.0.2-1 librsvg2-bin && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pcb_worker/ /app/pcb_worker/
USER 10001:10001
ENV HOME=/tmp XDG_CONFIG_HOME=/tmp/config XDG_CACHE_HOME=/tmp/cache
CMD ["/usr/bin/python3", "-m", "pcb_worker.server"]
