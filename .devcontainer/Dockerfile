FROM homeassistant/home-assistant:stable
RUN apk add --no-cache fish nodejs npm github-cli \
 && npm install -g @anthropic-ai/claude-code \
 && sed -i 's|/bin/ash|/usr/bin/fish|' /etc/passwd
