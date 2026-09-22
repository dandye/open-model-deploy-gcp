FROM python:3.11-slim

RUN mkdir -p /usr/local/lib/node_modules
COPY assets/node_modules.tar.gz /tmp/node_modules.tar.gz
RUN tar --no-same-owner -xzf /tmp/node_modules.tar.gz -C /usr/local/lib/node_modules && rm /tmp/node_modules.tar.gz

COPY assets/bin/node /usr/local/bin/node
COPY assets/bin/claude.exe /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe

RUN ln -sf /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/local/bin/claude && \
    ln -sf /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/local/bin/claude-code && \
    chmod +x /usr/local/bin/node /usr/local/bin/claude /usr/local/bin/claude-code

WORKDIR /workspace
