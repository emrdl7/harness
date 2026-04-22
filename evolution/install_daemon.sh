#!/bin/bash
# harness idle runner를 macOS LaunchAgent로 등록
HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.harness.idle_runner.plist"
PYTHON="$HARNESS_DIR/.venv/bin/python"
LOG="$HOME/.harness/evolution/idle_runner.log"

mkdir -p "$HOME/.harness/evolution"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.harness.idle_runner</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$HARNESS_DIR/evolution/idle_runner.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$HARNESS_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$HARNESS_DIR</string>
    </dict>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null
launchctl load "$PLIST_PATH"
echo "✓ idle runner 데몬 등록 완료"
echo "  로그: $LOG"
echo "  중지: launchctl unload $PLIST_PATH"
