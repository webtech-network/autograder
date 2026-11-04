# Student runtime for `cpp` and `c`: GCC from Alpine 3.24 (musl).
# Built without a build context (see scripts/sandbox_images.py); never COPY or ADD.
FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a

LABEL autograder.runtime.languages="cpp,c"

# The compiler toolchain is installed, then the package manager is removed:
# no package managers or downloaders, no setuid binaries, an unprivileged user.
RUN apk add --no-cache gcc g++ make musl-dev \
    && rm -rf /sbin/apk /etc/apk /lib/apk /usr/share/apk /var/cache/apk \
    && rm -f /usr/bin/wget /usr/bin/curl /usr/bin/nc \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} + \
    && addgroup -S sandbox && adduser -S sandbox -G sandbox \
    && mkdir -p /app && chown sandbox:sandbox /app

WORKDIR /app
# Pools always mount a bounded tmpfs here (sandbox_manager/docker_profile.py).
VOLUME ["/app"]
USER sandbox
CMD ["g++", "--version"]
