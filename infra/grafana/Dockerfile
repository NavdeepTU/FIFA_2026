# Bakes provisioning config into the image rather than relying on a mounted volume
# or persistent disk -- the Grafana Container App has neither (min_replicas = 0,
# ephemeral filesystem), and a paid persistent-storage add-on wasn't worth it for a
# handful of config files that rarely change. Same "config lives in the image" idea
# as backend/Dockerfile, just for a third-party image instead of this project's own.
FROM grafana/grafana-oss:11.3.0

COPY provisioning /etc/grafana/provisioning
