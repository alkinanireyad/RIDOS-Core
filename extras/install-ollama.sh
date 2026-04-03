#!/bin/bash
# install-ollama.sh — RIDOS-Core 1.0 Nova
# Optional: installs Ollama + Phi-3 mini (fast, 2GB) for offline AI
set -e

GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GRN}[RIDOS-AI]${NC} $*"; }
warn()  { echo -e "${YLW}[WARN]${NC}    $*"; }
error() { echo -e "${RED}[ERROR]${NC}   $*"; exit 1; }

info "Installing Ollama AI for RIDOS-Core..."

# Check RAM
RAM_GB=$(awk '/MemTotal/{printf "%d", $2/1024/1024}' /proc/meminfo)
if [ "$RAM_GB" -lt 4 ]; then
    warn "Only ${RAM_GB}GB RAM detected. Ollama works best with 4GB+."
    warn "Continuing anyway — use Phi-3 mini (2GB model)."
fi

# Install Ollama
info "Downloading Ollama..."
curl -fsSL https://ollama.ai/install.sh | sh

# Start service
info "Starting Ollama service..."
systemctl enable ollama 2>/dev/null || true
systemctl start  ollama 2>/dev/null || true
sleep 3

# Pull Phi-3 mini (fast, lightweight, 2GB)
info "Pulling Phi-3 mini model (~2GB download)..."
ollama pull phi3:mini || warn "Model pull failed — run 'ollama pull phi3:mini' manually."

# Create RIDOS AI wrapper
cat > /opt/ridos-core/bin/ridos-ai.sh << 'EOF'
#!/bin/bash
# RIDOS-Core AI Assistant
# Usage: ridos-ai "your question"
#        ridos-ai  (interactive mode)
MODEL="${RIDOS_AI_MODEL:-phi3:mini}"

if [ -n "$1" ]; then
    ollama run "$MODEL" "$*"
else
    echo "RIDOS-Core AI Assistant (model: $MODEL)"
    echo "Type 'exit' to quit."
    ollama run "$MODEL"
fi
EOF
chmod +x /opt/ridos-core/bin/ridos-ai.sh

# Desktop shortcut
cat > /usr/share/applications/ridos-ai.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=RIDOS AI Assistant
Comment=Offline AI powered by Ollama + Phi-3
Exec=bash -c 'gnome-terminal -- /opt/ridos-core/bin/ridos-ai.sh'
Icon=utilities-terminal
Terminal=false
Categories=Utility;AI;
EOF

info ""
info "Ollama AI installed successfully!"
info "  Interactive: ridos-ai"
info "  One-shot:    ridos-ai 'what is the weather like?'"
info "  Change model: export RIDOS_AI_MODEL=llama3"
