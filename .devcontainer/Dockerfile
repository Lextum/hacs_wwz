FROM homeassistant/home-assistant:stable
RUN apk add --no-cache fish nodejs npm github-cli \
 && adduser -D -s /usr/bin/fish vscode \
 && chown -R vscode:vscode /config

USER vscode
RUN npm config set prefix ~/.npm-global \
 && npm install -g @anthropic-ai/claude-code
ENV PATH="/home/vscode/.npm-global/bin:${PATH}"
