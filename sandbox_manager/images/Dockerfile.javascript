FROM node:18-alpine

RUN addgroup -S sandbox && adduser -S sandbox -G sandbox

# Remove npm/yarn to prevent students from installing packages at runtime
# (Pre-install allowed packages before this step if needed)
RUN npm uninstall -g npm yarn \
    && rm -rf /usr/local/lib/node_modules/npm \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn

# Hardening
RUN rm -f /usr/bin/wget /usr/bin/curl /usr/bin/nc
RUN find / -perm /6000 -type f -exec chmod a-s {} \; || true

WORKDIR /app
RUN chown sandbox:sandbox /app

VOLUME ["/app"]

USER sandbox
CMD ["node"]
