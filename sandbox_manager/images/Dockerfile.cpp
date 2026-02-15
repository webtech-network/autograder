FROM alpine:3.18

# Install Build Tools
RUN apk add --no-cache gcc g++ make musl-dev

# Create User
RUN addgroup -S sandbox && adduser -S sandbox -G sandbox

# Security: Remove APK (Package Manager) so they can't install tools
# We assume gcc/g++ are the only tools they need.
RUN rm -rf /sbin/apk /etc/apk /lib/apk /usr/share/apk

# Remove network downloaders
RUN rm -f /usr/bin/wget /usr/bin/curl /usr/bin/nc

WORKDIR /app
RUN chown sandbox:sandbox /app

VOLUME ["/app"]

USER sandbox

# Default command helps verify compiler version
CMD ["g++", "--version"]
