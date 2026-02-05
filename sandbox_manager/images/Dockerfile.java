FROM eclipse-temurin:17-jdk-alpine

RUN addgroup -S sandbox && adduser -S sandbox -G sandbox

# Hardening
RUN rm -f /usr/bin/wget /usr/bin/curl /usr/bin/nc
RUN find / -perm /6000 -type f -exec chmod a-s {} \; || true

WORKDIR /app
RUN chown sandbox:sandbox /app

USER sandbox
CMD ["jshell"]