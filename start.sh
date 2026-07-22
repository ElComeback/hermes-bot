#!/bin/bash
set -e

# Create Hermes config directory
mkdir -p ~/.hermes

# Write config.yaml
cat > ~/.hermes/config.yaml << 'EOF'
model:
  default: deepseek-chat
  provider: deepseek
  base_url: https://api.deepseek.com
agent:
  max_turns: 150
terminal:
  backend: local
  timeout: 60
EOF

# Write .env with API keys from Railway env vars
cat > ~/.hermes/.env << ENVEOF
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS:-}
ENVEOF

# Start the bot
exec python bot.py
