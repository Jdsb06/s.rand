#!/bin/bash
PROJECT_DIR="/home/jdsb/Desktop/BiULding/projects/light"
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
source venv/bin/activate

# Cleanup function to kill all server and browser processes
cleanup() {
    trap - INT TERM EXIT HUP
    echo ""
    echo "🛑 Shutting down Ambient Light Sync..."
    
    if [ -n "$BROWSER_PID" ]; then
        kill -9 "$BROWSER_PID" 2>/dev/null
    fi
    pkill -9 -P $$ 2>/dev/null
    pkill -9 -f "ambient_server.py" 2>/dev/null
    pkill -9 -f "light-sync-chrome-profile" 2>/dev/null
    pkill -9 -f "sync.html" 2>/dev/null
    
    echo "✅ All related processes (Python & Chrome) stopped."
    exit 0
}

# Trap INT (Ctrl+C), TERM, EXIT, and HUP signals
trap cleanup INT TERM EXIT HUP

echo "==========================================="
echo "💡 Ambient Light Sync Server"
echo "==========================================="

# Clean up any previous server/browser instances
pkill -9 -f "ambient_server.py" 2>/dev/null
pkill -9 -f "light-sync-chrome-profile" 2>/dev/null
sleep 0.5

HTML_FILE="file://$PROJECT_DIR/sync.html"

# Open sync.html in Chrome (App Mode) or fallback browser
if command -v google-chrome > /dev/null 2>&1; then
    google-chrome --user-data-dir=/tmp/light-sync-chrome-profile --app="$HTML_FILE" > /dev/null 2>&1 &
    BROWSER_PID=$!
elif command -v google-chrome-stable > /dev/null 2>&1; then
    google-chrome-stable --user-data-dir=/tmp/light-sync-chrome-profile --app="$HTML_FILE" > /dev/null 2>&1 &
    BROWSER_PID=$!
elif command -v firefox > /dev/null 2>&1; then
    firefox --new-window "$HTML_FILE" > /dev/null 2>&1 &
    BROWSER_PID=$!
elif command -v xdg-open > /dev/null 2>&1; then
    xdg-open "$HTML_FILE" > /dev/null 2>&1 &
    BROWSER_PID=$!
fi

echo "🌐 Opened sync.html in your browser!"
echo "Ready! Click 'Select Screen to Sync' in the browser."
echo "📌 Server running in foreground. Press Ctrl+C at any time to stop."
echo "-------------------------------------------"

# Run Python server in foreground. When interrupted (Ctrl+C), python exits and cleanup executes.
python -u ambient_server.py

# Explicit cleanup invocation after python exits
cleanup
