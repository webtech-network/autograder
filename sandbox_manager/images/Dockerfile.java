# Student runtime for `java`: Eclipse Temurin JDK 21 (LTS) on Alpine 3.24.
# Built without a build context (see scripts/sandbox_images.py); never COPY or ADD.
FROM eclipse-temurin:21-jdk-alpine-3.24@sha256:b78a1d385da875588e21207f07dddf9a1418849971ae857fb24c8f3a7d441a72

LABEL autograder.runtime.languages="java"

# Students get the JDK only: no package managers or downloaders, no setuid
# binaries, and an unprivileged user.
RUN rm -rf /sbin/apk /etc/apk /lib/apk /usr/share/apk /var/cache/apk \
    && rm -f /usr/bin/wget /usr/bin/curl /usr/bin/nc \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} + \
    && addgroup -S sandbox && adduser -S sandbox -G sandbox \
    && mkdir -p /app && chown sandbox:sandbox /app

WORKDIR /app
# Pools always mount a bounded tmpfs here (sandbox_manager/docker_profile.py).
VOLUME ["/app"]
USER sandbox
CMD ["jshell"]
