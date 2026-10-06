#!/usr/bin/env bash
# ============================================================
# SVM AI — Automatic Installer + LocalAI Auto-Setup
# Made by AnkitCoder
# Supports: VPS | Pterodactyl | Docker | GitHub upgrade
# ============================================================
set -euo pipefail

SVMAI_VERSION="1.1.0"
SVMAI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SVMAI_DIR}/.env"
ENV_EXAMPLE="${SVMAI_DIR}/.env.example"
DATA_DIR="${SVMAI_DIR}/data"
WORKSPACE_DIR="${SVMAI_DIR}/workspace"
LOG_DIR="${SVMAI_DIR}/logs"
VENV_DIR="${SVMAI_DIR}/.venv"
LOCALAI_DIR="${SVMAI_DIR}/localai"
LOCALAI_MODELS_DIR="${LOCALAI_DIR}/models"
LOCALAI_DEFAULT_URL="http://127.0.0.1:8080"
LOCALAI_PORT=8080
# Optional: set GITHUB_REPO to enable --upgrade from your fork
GITHUB_REPO="${GITHUB_REPO:-}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"

# Colors
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; B='\033[0;34m'; C='\033[0;36m'; N='\033[0m'
BOLD='\033[1m'

info()  { echo -e "${B}[INFO]${N} $*"; }
ok()    { echo -e "${G}[ OK ]${N} $*"; }
warn()  { echo -e "${Y}[WARN]${N} $*"; }
fail()  { echo -e "${R}[FAIL]${N} $*"; }
step()  { echo -e "\n${C}${BOLD}[$*]${N}"; }

banner() {
  echo -e "${C}"
  cat << 'EOF'
╔════════════════════════════════════════════╗
║            S V M   A I                     ║
║          Made by AnkitCoder                ║
║     AUTONOMOUS DISCORD AI AGENT            ║
║     LocalAI Auto-Install · VPS/Ptero       ║
╚════════════════════════════════════════════╝
EOF
  echo -e "${N}"
}

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
detect_os() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_VERSION="${VERSION_ID:-}"
  else
    OS_ID="$(uname -s | tr '[:upper:]' '[:lower:]')"
    OS_VERSION=""
  fi
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) ARCH_NORM="amd64" ;;
    aarch64|arm64) ARCH_NORM="arm64" ;;
    *) ARCH_NORM="$ARCH" ;;
  esac
}

detect_resources() {
  CPU_CORES="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)"
  if command -v free >/dev/null 2>&1; then
    RAM_MB="$(free -m | awk '/^Mem:/{print $2}')"
  else
    RAM_MB=0
  fi
  DISK_GB="$(df -BG "$SVMAI_DIR" 2>/dev/null | awk 'NR==2{gsub(/G/,"",$4); print $4}' || echo 0)"
  GPU_INFO="none"
  CUDA_AVAILABLE=false
  CUDA_MAJOR=""
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_INFO="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo nvidia)"
    CUDA_AVAILABLE=true
    CUDA_MAJOR="$(nvidia-smi | grep -oE 'CUDA Version: [0-9]+' | head -1 | grep -oE '[0-9]+' || echo 12)"
  fi
}

detect_python() {
  PYTHON=""
  for cand in python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
      PYTHON="$(command -v "$cand")"
      break
    fi
  done
  PIP=""
  [[ -n "$PYTHON" ]] && PIP="$PYTHON -m pip"
}

detect_docker() {
  DOCKER_AVAILABLE=false
  DOCKER_CAN_RUN=false
  if command -v docker >/dev/null 2>&1; then
    DOCKER_AVAILABLE=true
    if docker info >/dev/null 2>&1; then
      DOCKER_CAN_RUN=true
    fi
  fi
}

detect_pterodactyl() {
  IS_PTERODACTYL=false
  PTERO_HOME=""
  if [[ -d /home/container ]]; then
    IS_PTERODACTYL=true
    PTERO_HOME="/home/container"
  fi
  if [[ -n "${P_SERVER_UUID:-}" ]] || [[ -n "${PTERODACTYL:-}" ]]; then
    IS_PTERODACTYL=true
  fi
  if [[ -n "${SERVER_MEMORY:-}" ]] && [[ -d /home/container ]]; then
    IS_PTERODACTYL=true
    PTERO_HOME="/home/container"
  fi
}

detect_localai() {
  LOCALAI_RUNNING=false
  LOCALAI_DOCKER=false
  LOCALAI_BINARY=false
  LOCALAI_URL="${LOCALAI_URL:-$LOCALAI_DEFAULT_URL}"
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$ENV_FILE" 2>/dev/null || true; set +a
    LOCALAI_URL="${LOCALAI_URL:-$LOCALAI_DEFAULT_URL}"
  fi
  if curl -sf --max-time 3 "${LOCALAI_URL}/readyz" >/dev/null 2>&1 || \
     curl -sf --max-time 3 "${LOCALAI_URL}/v1/models" >/dev/null 2>&1; then
    LOCALAI_RUNNING=true
  fi
  if $DOCKER_CAN_RUN; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qiE '^local-ai$|^localai$'; then
      LOCALAI_DOCKER=true
      LOCALAI_RUNNING=true
    fi
  fi
  if [[ -f "${LOCALAI_DIR}/local-ai" ]] || [[ -f "${LOCALAI_DIR}/localai" ]]; then
    LOCALAI_BINARY=true
  fi
}

# Pick model size from RAM (MB)
recommend_model() {
  # Returns gallery-friendly model name suitable for auto-install
  if [[ "${RAM_MB:-0}" -ge 16000 ]]; then
    echo "llama3.2-3b-instruct:q4_k_m"
  elif [[ "${RAM_MB:-0}" -ge 8000 ]]; then
    echo "qwen2.5-1.5b-instruct"
  elif [[ "${RAM_MB:-0}" -ge 4000 ]]; then
    echo "tinyllama-chat"
  else
    echo "tinyllama-chat"
  fi
}

# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------
ensure_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
      cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
      touch "$ENV_FILE"
    fi
  fi
}

update_env_var() {
  local key="$1" val="$2"
  ensure_env_file
  if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    local current
    current=$(grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2-)
    # Never overwrite existing Discord secrets
    if [[ "$key" == "DISCORD_TOKEN" && -n "$current" ]]; then
      return 0
    fi
    if [[ "$key" == "ADMIN_IDS" && -n "$current" ]]; then
      return 0
    fi
    if [[ "$key" == "SEARCH_API_KEY" && -n "$current" ]]; then
      return 0
    fi
    if [[ "$key" == "IMAGE_API_KEY" && -n "$current" ]]; then
      return 0
    fi
    if [[ "$key" == "LOCALAI_API_KEY" && -n "$current" ]]; then
      return 0
    fi
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE" 2>/dev/null || \
      sed -i '' "s|^${key}=.*|${key}=${val}|" "$ENV_FILE" 2>/dev/null || true
    rm -f "${ENV_FILE}.bak" 2>/dev/null || true
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

# ---------------------------------------------------------------------------
# GitHub upgrade
# ---------------------------------------------------------------------------
cmd_upgrade() {
  step "GitHub upgrade"
  if [[ -z "$GITHUB_REPO" ]]; then
    if [[ -d "${SVMAI_DIR}/.git" ]]; then
      info "Local git repo detected — pulling latest..."
      # Backup user data first
      cmd_backup
      git -C "$SVMAI_DIR" fetch --all 2>/dev/null || true
      git -C "$SVMAI_DIR" pull --ff-only origin "${GITHUB_BRANCH}" 2>/dev/null || \
        git -C "$SVMAI_DIR" pull --ff-only 2>/dev/null || {
          warn "git pull failed — check remote / conflicts"
          return 1
        }
      ok "Code updated from git"
      info "Re-running repair to refresh deps + LocalAI config..."
      NON_INTERACTIVE=1 cmd_repair
      return 0
    fi
    warn "No GITHUB_REPO set and not a git clone."
    warn "Set: export GITHUB_REPO=https://github.com/USER/svm-ai.git"
    warn "Or:  git clone <repo> && bash install.sh --upgrade"
    return 1
  fi
  cmd_backup
  info "Cloning/updating from $GITHUB_REPO ($GITHUB_BRANCH)..."
  TMP_UP="${SVMAI_DIR}/.upgrade_tmp"
  rm -rf "$TMP_UP"
  git clone --depth 1 --branch "$GITHUB_BRANCH" "$GITHUB_REPO" "$TMP_UP" || {
    fail "Clone failed"
    return 1
  }
  # Preserve user files
  for keep in .env data workspace logs .venv localai; do
    if [[ -e "${SVMAI_DIR}/${keep}" ]]; then
      rm -rf "${TMP_UP}/${keep}" 2>/dev/null || true
    fi
  done
  # Copy new code over (files only, not protected dirs)
  for f in bot.py install.sh requirements.txt .env.example README.md Dockerfile; do
    if [[ -f "${TMP_UP}/${f}" ]]; then
      cp -f "${TMP_UP}/${f}" "${SVMAI_DIR}/${f}"
      ok "Updated $f"
    fi
  done
  rm -rf "$TMP_UP"
  chmod +x "${SVMAI_DIR}/install.sh"
  info "Refreshing Python deps..."
  NON_INTERACTIVE=1 install_python_deps
  detect_localai
  if ! $LOCALAI_RUNNING; then
    install_localai_full
  fi
  detect_and_select_models
  ok "Upgrade complete"
}

# ---------------------------------------------------------------------------
# Python deps
# ---------------------------------------------------------------------------
install_python_deps() {
  step "Installing Python dependencies"
  if [[ -z "${PYTHON:-}" ]]; then
    detect_python
  fi
  if [[ -z "$PYTHON" ]]; then
    fail "Python 3 not found. Install Python 3.10+ and re-run."
    return 1
  fi
  ok "Python: $($PYTHON --version 2>&1)"

  if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment..."
    if ! $PYTHON -m venv "$VENV_DIR" 2>/dev/null; then
      warn "venv failed — installing with --user"
      $PIP install --user -U pip setuptools wheel 2>/dev/null || true
      $PIP install --user -r "${SVMAI_DIR}/requirements.txt"
      return 0
    fi
  fi
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  pip install -U pip setuptools wheel >/dev/null
  pip install -r "${SVMAI_DIR}/requirements.txt"
  ok "Python dependencies installed"
}

# ---------------------------------------------------------------------------
# LOCALAI — FULL AUTOMATIC INSTALL
# ---------------------------------------------------------------------------
install_localai_full() {
  step "LocalAI automatic install & configure"
  detect_localai
  detect_resources
  detect_docker
  detect_pterodactyl

  if $LOCALAI_RUNNING; then
    ok "LocalAI already running at ${LOCALAI_URL}"
    return 0
  fi

  # -------- Pterodactyl path --------
  if $IS_PTERODACTYL; then
    info "Pterodactyl panel detected."
    info "Inside eggs, Docker-in-Docker is usually blocked."
    info "SVM AI will use EXTERNAL LocalAI."
    echo
    if [[ "${NON_INTERACTIVE:-0}" == "1" ]]; then
      # Keep default or existing
      update_env_var "LOCALAI_URL" "${LOCALAI_URL}"
      warn "Set LOCALAI_URL in .env to your host LocalAI (e.g. http://YOUR_VPS_IP:8080)"
      warn "Or run LocalAI on the same machine host network and point to it."
      return 0
    fi
    echo "Options for Pterodactyl:"
    echo "  1) LocalAI already running on host / another VPS (recommended)"
    echo "  2) Try official LocalAI install script (binary, no Docker)"
    echo "  3) Skip — configure LOCALAI_URL later in .env"
    echo -n "Choice [1/2/3]: "
    read -r pchoice
    case "${pchoice:-1}" in
      2)
        install_localai_official_script
        ;;
      3)
        warn "Skipped. Edit .env → LOCALAI_URL=http://IP:8080"
        ;;
      *)
        echo -n "Enter LocalAI URL (e.g. http://1.2.3.4:8080): "
        read -r ext_url
        if [[ -n "$ext_url" ]]; then
          LOCALAI_URL="$ext_url"
          update_env_var "LOCALAI_URL" "$LOCALAI_URL"
          if curl -sf --max-time 5 "${LOCALAI_URL}/v1/models" >/dev/null 2>&1; then
            ok "External LocalAI reachable"
            LOCALAI_RUNNING=true
          else
            warn "URL saved but not reachable yet — start LocalAI on that host"
          fi
        fi
        ;;
    esac
    return 0
  fi

  # -------- VPS / normal Linux --------
  # Prefer Docker AIO (models included / auto)
  if $DOCKER_CAN_RUN; then
    install_localai_docker_aio
    return $?
  fi

  # Try install Docker first (VPS only, if root-ish)
  if ! $DOCKER_AVAILABLE && [[ "$(id -u)" -eq 0 || -n "${SUDO_USER:-}" ]]; then
    info "Docker not found — attempting to install Docker Engine..."
    if install_docker_engine; then
      detect_docker
      if $DOCKER_CAN_RUN; then
        install_localai_docker_aio
        return $?
      fi
    fi
  fi

  # Official LocalAI one-liner / binary
  install_localai_official_script
}

install_docker_engine() {
  if command -v apt-get >/dev/null 2>&1; then
    info "Installing Docker via apt..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg 2>/dev/null || true
    install -m 0755 -d /etc/apt/keyrings
    if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg 2>/dev/null | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
    fi
    # Fallback: get.docker.com
    curl -fsSL https://get.docker.com | sh 2>/dev/null || {
      warn "Docker install script failed"
      return 1
    }
    systemctl enable --now docker 2>/dev/null || service docker start 2>/dev/null || true
    ok "Docker installed"
    return 0
  fi
  # Generic
  curl -fsSL https://get.docker.com | sh 2>/dev/null || return 1
  systemctl enable --now docker 2>/dev/null || true
  return 0
}

install_localai_docker_aio() {
  info "Installing LocalAI via Docker (All-in-One recommended)..."
  mkdir -p "$LOCALAI_MODELS_DIR"

  # Choose image
  local IMAGE="localai/localai:latest-aio-cpu"
  local RUN_EXTRA=()
  if $CUDA_AVAILABLE; then
    if [[ "${CUDA_MAJOR:-12}" -ge 13 ]]; then
      IMAGE="localai/localai:latest-aio-gpu-nvidia-cuda-13"
    else
      IMAGE="localai/localai:latest-aio-gpu-nvidia-cuda-12"
    fi
    RUN_EXTRA+=(--gpus all)
    info "NVIDIA GPU detected → $IMAGE"
  else
    info "CPU mode → $IMAGE"
  fi

  # Stop/remove old container if exists but not running properly
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'local-ai'; then
    info "Existing local-ai container found — restarting..."
    docker start local-ai 2>/dev/null || {
      docker rm -f local-ai 2>/dev/null || true
      _docker_run_localai "$IMAGE" "${RUN_EXTRA[@]}"
    }
  else
    _docker_run_localai "$IMAGE" "${RUN_EXTRA[@]}"
  fi

  LOCALAI_URL="http://127.0.0.1:${LOCALAI_PORT}"
  update_env_var "LOCALAI_URL" "$LOCALAI_URL"

  info "Waiting for LocalAI API (models may download on first boot)..."
  local ready=false
  for i in $(seq 1 60); do
    if curl -sf --max-time 3 "${LOCALAI_URL}/readyz" >/dev/null 2>&1 || \
       curl -sf --max-time 3 "${LOCALAI_URL}/v1/models" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 3
    if (( i % 10 == 0 )); then
      info "Still waiting... (${i}/60) — first start can take several minutes"
    fi
  done

  if $ready; then
    ok "LocalAI is online at ${LOCALAI_URL}"
    LOCALAI_RUNNING=true
    # Auto-install a small model if gallery empty
    auto_install_model_if_needed
    return 0
  fi

  warn "LocalAI container started but API not ready yet."
  warn "Check: docker logs local-ai"
  warn "It may still be pulling models. Re-run: bash install.sh --localai-status"
  LOCALAI_RUNNING=false
  return 0
}

_docker_run_localai() {
  local IMAGE="$1"
  shift
  local EXTRA=("$@")
  # Gallery model hint via command args (AIO may already include models)
  local MODEL_HINT
  MODEL_HINT="$(recommend_model)"
  info "Pulling image $IMAGE (this can take a while)..."
  docker pull "$IMAGE" || warn "Pull warning — will try run anyway"

  docker run -d --name local-ai \
    -p "${LOCALAI_PORT}:8080" \
    -v localai-models:/models \
    -v localai-backends:/backends \
    -e DEBUG=false \
    -e THREADS="${CPU_CORES:-4}" \
    --restart unless-stopped \
    "${EXTRA[@]}" \
    "$IMAGE" \
    2>/dev/null || {
      # Fallback without AIO / without GPU flags
      warn "Primary run failed — trying plain CPU image..."
      docker rm -f local-ai 2>/dev/null || true
      docker run -d --name local-ai \
        -p "${LOCALAI_PORT}:8080" \
        -v localai-models:/models \
        --restart unless-stopped \
        localai/localai:latest \
        || {
          fail "Could not start LocalAI container"
          return 1
        }
    }
  ok "Container local-ai created"
}

install_localai_official_script() {
  info "Installing LocalAI via official install script (https://localai.io/install.sh)..."
  mkdir -p "$LOCALAI_DIR" "$LOCALAI_MODELS_DIR"

  # Use official installer with Docker if possible, else binary
  export DOCKER_INSTALL="${DOCKER_INSTALL:-false}"
  if $DOCKER_CAN_RUN; then
    export DOCKER_INSTALL=true
    export USE_AIO=true
  fi
  export PORT="${LOCALAI_PORT}"
  export MODELS_PATH="${LOCALAI_MODELS_DIR}"

  if curl -fsSL https://localai.io/install.sh | bash; then
    ok "Official LocalAI installer finished"
  else
    warn "Official installer had issues — trying direct binary download..."
    install_localai_binary
    return $?
  fi

  # Discover where binary landed
  local bin=""
  for c in local-ai localai \
           /usr/local/bin/local-ai /usr/bin/local-ai \
           "${HOME}/.local/bin/local-ai" \
           "${LOCALAI_DIR}/local-ai"; do
    if command -v "$c" >/dev/null 2>&1; then
      bin="$(command -v "$c")"
      break
    fi
    if [[ -x "$c" ]]; then
      bin="$c"
      break
    fi
  done

  if [[ -n "$bin" ]]; then
    info "Starting LocalAI binary: $bin"
    nohup "$bin" run --address "0.0.0.0:${LOCALAI_PORT}" \
      --models-path "$LOCALAI_MODELS_DIR" \
      > "${LOG_DIR}/localai.log" 2>&1 &
    echo $! > "${LOCALAI_DIR}/localai.pid"
    sleep 5
  fi

  LOCALAI_URL="http://127.0.0.1:${LOCALAI_PORT}"
  update_env_var "LOCALAI_URL" "$LOCALAI_URL"

  for i in $(seq 1 40); do
    if curl -sf --max-time 3 "${LOCALAI_URL}/v1/models" >/dev/null 2>&1; then
      ok "LocalAI binary API ready"
      LOCALAI_RUNNING=true
      auto_install_model_if_needed
      return 0
    fi
    sleep 2
  done
  warn "LocalAI may still be starting. Check ${LOG_DIR}/localai.log"
  return 0
}

install_localai_binary() {
  info "Downloading LocalAI binary for linux-${ARCH_NORM}..."
  mkdir -p "$LOCALAI_DIR" "$LOCALAI_MODELS_DIR"
  local api="https://api.github.com/repos/mudler/LocalAI/releases/latest"
  local url
  url=$(curl -fsSL "$api" 2>/dev/null \
    | grep -oE "https://github.com/mudler/LocalAI/releases/download/[^\"]+LocalAI[^\"]*linux[-_]${ARCH_NORM}[^\"]*" \
    | head -1 || true)
  # Alternate pattern
  if [[ -z "$url" ]]; then
    url=$(curl -fsSL "$api" 2>/dev/null \
      | grep -oE "https://github.com/mudler/LocalAI/releases/download/[^\"]+linux-${ARCH_NORM}[^\"]*" \
      | head -1 || true)
  fi
  if [[ -z "$url" ]]; then
    fail "Could not find LocalAI binary URL for ${ARCH_NORM}"
    fail "Manual: https://github.com/mudler/LocalAI/releases"
    return 1
  fi
  info "Download: $url"
  curl -L --progress-bar -o "${LOCALAI_DIR}/local-ai" "$url" || return 1
  chmod +x "${LOCALAI_DIR}/local-ai"
  nohup "${LOCALAI_DIR}/local-ai" --address "0.0.0.0:${LOCALAI_PORT}" \
    --models-path "$LOCALAI_MODELS_DIR" \
    > "${LOG_DIR}/localai.log" 2>&1 &
  echo $! > "${LOCALAI_DIR}/localai.pid"
  LOCALAI_URL="http://127.0.0.1:${LOCALAI_PORT}"
  update_env_var "LOCALAI_URL" "$LOCALAI_URL"
  sleep 4
  ok "Binary started (PID $(cat "${LOCALAI_DIR}/localai.pid" 2>/dev/null || echo ?))"
}

auto_install_model_if_needed() {
  info "Checking models on LocalAI..."
  local models_json
  models_json=$(curl -sf --max-time 15 "${LOCALAI_URL}/v1/models" 2>/dev/null || echo '{}')
  local count
  count=$(echo "$models_json" | grep -c '"id"' || echo 0)
  if [[ "${count:-0}" -gt 0 ]]; then
    ok "Models already present ($count)"
    return 0
  fi

  # Try gallery install via LocalAI models API / run endpoint if available
  local MODEL
  MODEL="$(recommend_model)"
  info "No models found — requesting gallery model: $MODEL"
  info "RAM=${RAM_MB}MB → recommended lightweight model"

  # Method 1: POST to models endpoint (newer LocalAI)
  curl -sf --max-time 120 -X POST "${LOCALAI_URL}/models/apply" \
    -H "Content-Type: application/json" \
    -d "{\"id\":\"${MODEL}\"}" >/dev/null 2>&1 || true

  # Method 2: docker exec into container and run CLI
  if $DOCKER_CAN_RUN && docker ps --format '{{.Names}}' | grep -qx local-ai; then
    info "Trying model install inside container..."
    docker exec local-ai local-ai models install "$MODEL" 2>/dev/null || \
    docker exec local-ai /local-ai models install "$MODEL" 2>/dev/null || \
    docker exec local-ai local-ai run "$MODEL" 2>/dev/null || true
  fi

  sleep 5
  models_json=$(curl -sf --max-time 15 "${LOCALAI_URL}/v1/models" 2>/dev/null || echo '{}')
  count=$(echo "$models_json" | grep -c '"id"' || echo 0)
  if [[ "${count:-0}" -gt 0 ]]; then
    ok "Model install succeeded ($count models)"
  else
    warn "Auto model install did not complete yet."
    warn "Open http://127.0.0.1:${LOCALAI_PORT} → Models → Install a small model"
    warn "Or: docker exec -it local-ai local-ai models install tinyllama-chat"
  fi
}

detect_and_select_models() {
  step "Detecting & selecting AI models"
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE" 2>/dev/null || true; set +a
  LOCALAI_URL="${LOCALAI_URL:-$LOCALAI_DEFAULT_URL}"

  if ! curl -sf --max-time 8 "${LOCALAI_URL}/v1/models" >/dev/null 2>&1; then
    warn "LocalAI not reachable at ${LOCALAI_URL} — model selection skipped"
    update_env_var "LOCALAI_URL" "$LOCALAI_URL"
    return 0
  fi

  local MODELS_JSON MODEL_LIST
  MODELS_JSON=$(curl -sf --max-time 15 "${LOCALAI_URL}/v1/models" 2>/dev/null || echo '{}')
  MODEL_LIST=$(echo "$MODELS_JSON" | grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]+"' | sed 's/.*:"//;s/"$//' || true)

  if [[ -z "$MODEL_LIST" ]]; then
    warn "No models listed yet. AIO image may still be downloading."
    auto_install_model_if_needed
    MODELS_JSON=$(curl -sf --max-time 15 "${LOCALAI_URL}/v1/models" 2>/dev/null || echo '{}')
    MODEL_LIST=$(echo "$MODELS_JSON" | grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]+"' | sed 's/.*:"//;s/"$//' || true)
  fi

  if [[ -z "$MODEL_LIST" ]]; then
    warn "Still no models. Bot will start; add models then re-run: bash install.sh --localai-models"
    return 0
  fi

  ok "Available models:"
  echo "$MODEL_LIST" | while read -r m; do [[ -n "$m" ]] && echo "  • $m"; done

  local GENERAL="" CODING="" REASONING="" VISION="" IMAGE=""
  while read -r m; do
    [[ -z "$m" ]] && continue
    local ml
    ml=$(echo "$m" | tr '[:upper:]' '[:lower:]')
    [[ -z "$GENERAL" ]] && GENERAL="$m"
    if [[ -z "$CODING" && ( "$ml" == *code* || "$ml" == *coder* || "$ml" == *deepseek* || "$ml" == *starcoder* ) ]]; then
      CODING="$m"
    fi
    if [[ -z "$REASONING" && ( "$ml" == *reason* || "$ml" == *think* || "$ml" == *qwen* || "$ml" == *llama* || "$ml" == *mistral* || "$ml" == *phi* ) ]]; then
      REASONING="$m"
    fi
    if [[ -z "$VISION" && ( "$ml" == *vision* || "$ml" == *llava* || "$ml" == *bakllava* || "$ml" == *minicpm* || "$ml" == *moondream* ) ]]; then
      VISION="$m"
    fi
    if [[ -z "$IMAGE" && ( "$ml" == *sd* || "$ml" == *stable* || "$ml" == *flux* || "$ml" == *diffusion* || "$ml" == *image* ) ]]; then
      IMAGE="$m"
    fi
  done <<< "$MODEL_LIST"

  CODING="${CODING:-$GENERAL}"
  REASONING="${REASONING:-$GENERAL}"
  VISION="${VISION:-$GENERAL}"

  update_env_var "LOCALAI_URL" "$LOCALAI_URL"
  update_env_var "LOCALAI_MODEL" "$GENERAL"
  update_env_var "LOCALAI_GENERAL_MODEL" "$GENERAL"
  update_env_var "LOCALAI_CODING_MODEL" "$CODING"
  update_env_var "LOCALAI_REASONING_MODEL" "$REASONING"
  [[ -n "$VISION" ]] && update_env_var "LOCALAI_VISION_MODEL" "$VISION"
  [[ -n "$IMAGE" ]] && update_env_var "LOCALAI_IMAGE_MODEL" "$IMAGE"

  ok "Selected → general=$GENERAL | coding=$CODING | reasoning=$REASONING"
}

# ---------------------------------------------------------------------------
# Discord / tools config
# ---------------------------------------------------------------------------
configure_discord() {
  step "Configuring Discord"
  ensure_env_file
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE" 2>/dev/null || true; set +a

  if [[ -n "${DISCORD_TOKEN:-}" ]]; then
    ok "Discord token already set (preserved)"
  else
    if [[ "${NON_INTERACTIVE:-0}" == "1" ]]; then
      warn "NON_INTERACTIVE: set DISCORD_TOKEN in .env before starting"
    else
      echo -n "Discord Bot Token: "
      read -rs TOKEN_INPUT
      echo
      if [[ -n "$TOKEN_INPUT" ]]; then
        update_env_var "DISCORD_TOKEN" "$TOKEN_INPUT"
        ok "Token saved (not printed)"
      else
        warn "No token — edit .env later"
      fi
    fi
  fi

  if [[ -z "${ADMIN_IDS:-}" && "${NON_INTERACTIVE:-0}" != "1" ]]; then
    echo -n "Admin Discord User ID(s) (comma-separated, optional): "
    read -r ADMIN_INPUT || true
    [[ -n "${ADMIN_INPUT:-}" ]] && update_env_var "ADMIN_IDS" "$ADMIN_INPUT"
  fi
}

configure_tools() {
  step "Workspace & data"
  mkdir -p "$DATA_DIR" "$WORKSPACE_DIR" "$LOG_DIR" "$LOCALAI_MODELS_DIR"
  update_env_var "WORKSPACE_DIR" "./workspace"
  update_env_var "DATA_DIR" "./data"
  update_env_var "LOG_DIR" "./logs"
  ok "Directories ready"
}

run_health_checks() {
  step "Health checks"
  local pass=0

  if [[ -d "$VENV_DIR" ]]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate" 2>/dev/null || true
  fi
  if python -m py_compile "${SVMAI_DIR}/bot.py" 2>/dev/null; then
    ok "bot.py syntax"
    ((pass++)) || true
  else
    fail "bot.py syntax error"
  fi

  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE" 2>/dev/null || true; set +a
  LOCALAI_URL="${LOCALAI_URL:-$LOCALAI_DEFAULT_URL}"

  if curl -sf --max-time 5 "${LOCALAI_URL}/v1/models" >/dev/null 2>&1; then
    ok "LocalAI API @ $LOCALAI_URL"
    ((pass++)) || true
    local model="${LOCALAI_MODEL:-}"
    if [[ -z "$model" ]]; then
      model=$(curl -sf "${LOCALAI_URL}/v1/models" | grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]+"' | head -1 | sed 's/.*:"//;s/"$//')
    fi
    if [[ -n "$model" ]]; then
      local TEST_RESP
      TEST_RESP=$(curl -sf --max-time 90 -X POST "${LOCALAI_URL}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with OK only\"}],\"max_tokens\":8}" 2>/dev/null || true)
      if echo "$TEST_RESP" | grep -qiE 'ok|choices|content'; then
        ok "LocalAI chat test (model=$model)"
        ((pass++)) || true
      else
        warn "Chat test inconclusive — model may still be loading"
      fi
    fi
  else
    warn "LocalAI not reachable — start it or set LOCALAI_URL"
  fi

  [[ -d "$DATA_DIR" ]] && ok "Data dir" && ((pass++)) || true
  [[ -d "$WORKSPACE_DIR" ]] && ok "Workspace" && ((pass++)) || true
  echo
  info "Passed checks: $pass"
}

start_bot() {
  step "Starting SVM AI"
  if [[ "${NON_INTERACTIVE:-0}" == "1" ]]; then
    info "Non-interactive — start with: source .venv/bin/activate && python bot.py"
    return 0
  fi
  if [[ -d "$VENV_DIR" ]]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
  fi
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE" 2>/dev/null || true; set +a
  if [[ -z "${DISCORD_TOKEN:-}" ]]; then
    warn "DISCORD_TOKEN missing — edit .env then: python bot.py"
    return 0
  fi
  info "Launching bot (Ctrl+C to stop)..."
  exec python "${SVMAI_DIR}/bot.py"
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
cmd_doctor() {
  banner
  echo "SVM AI Doctor v${SVMAI_VERSION}"
  detect_os; detect_resources; detect_python; detect_docker; detect_pterodactyl; detect_localai
  echo
  printf "%-22s %s\n" "OS" "${OS_ID} ${OS_VERSION} (${ARCH_NORM})"
  printf "%-22s %s\n" "CPU cores" "$CPU_CORES"
  printf "%-22s %s\n" "RAM (MB)" "$RAM_MB"
  printf "%-22s %s\n" "Disk free (GB)" "$DISK_GB"
  printf "%-22s %s\n" "GPU" "$GPU_INFO"
  printf "%-22s %s\n" "CUDA" "$CUDA_AVAILABLE (${CUDA_MAJOR:-?})"
  printf "%-22s %s\n" "Python" "${PYTHON:-MISSING}"
  printf "%-22s %s\n" "Docker installed" "$DOCKER_AVAILABLE"
  printf "%-22s %s\n" "Docker runnable" "$DOCKER_CAN_RUN"
  printf "%-22s %s\n" "Pterodactyl" "$IS_PTERODACTYL"
  printf "%-22s %s\n" "LocalAI URL" "$LOCALAI_URL"
  printf "%-22s %s\n" "LocalAI running" "$LOCALAI_RUNNING"
  printf "%-22s %s\n" "LocalAI docker" "$LOCALAI_DOCKER"
  printf "%-22s %s\n" "Recommended model" "$(recommend_model)"
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$ENV_FILE" 2>/dev/null || true; set +a
    printf "%-22s %s\n" "Discord token" "$( [[ -n "${DISCORD_TOKEN:-}" ]] && echo SET || echo MISSING )"
  else
    printf "%-22s %s\n" ".env" "MISSING"
  fi
  echo
  if [[ -d "$VENV_DIR" ]]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate" 2>/dev/null || true
  fi
  if command -v python >/dev/null && python -m py_compile "${SVMAI_DIR}/bot.py" 2>/dev/null; then
    ok "bot.py compiles"
  else
    fail "bot.py compile failed"
  fi
  if $LOCALAI_RUNNING; then
    echo "--- models ---"
    curl -sf --max-time 5 "${LOCALAI_URL}/v1/models" 2>/dev/null | head -c 800 || true
    echo
  fi
}

cmd_status() {
  detect_docker; detect_localai
  echo "LocalAI URL : $LOCALAI_URL"
  echo "Running     : $LOCALAI_RUNNING"
  echo "Docker      : $LOCALAI_DOCKER"
  if $DOCKER_CAN_RUN; then
    docker ps --filter name=local-ai --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || true
  fi
  if $LOCALAI_RUNNING; then
    echo "--- /v1/models ---"
    curl -sf "${LOCALAI_URL}/v1/models" 2>/dev/null | head -c 1000 || true
    echo
  fi
  if [[ -f "${LOG_DIR}/svm_ai.log" ]]; then
    echo "--- bot log (tail) ---"
    tail -n 12 "${LOG_DIR}/svm_ai.log" 2>/dev/null || true
  fi
  if [[ -f "${LOG_DIR}/localai.log" ]]; then
    echo "--- localai log (tail) ---"
    tail -n 12 "${LOG_DIR}/localai.log" 2>/dev/null || true
  fi
}

cmd_repair() {
  info "Repair mode"
  detect_os; detect_resources; detect_python; detect_docker; detect_pterodactyl
  install_python_deps
  mkdir -p "$DATA_DIR" "$WORKSPACE_DIR" "$LOG_DIR" "$LOCALAI_MODELS_DIR"
  ensure_env_file
  detect_localai
  if ! $LOCALAI_RUNNING; then
    install_localai_full
  fi
  detect_and_select_models
  run_health_checks
  ok "Repair finished"
}

cmd_backup() {
  local BACKUP_DIR="${SVMAI_DIR}/backup_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$BACKUP_DIR"
  [[ -f "$ENV_FILE" ]] && cp "$ENV_FILE" "$BACKUP_DIR/"
  [[ -d "$DATA_DIR" ]] && cp -a "$DATA_DIR" "$BACKUP_DIR/" 2>/dev/null || true
  [[ -d "$WORKSPACE_DIR" ]] && cp -a "$WORKSPACE_DIR" "$BACKUP_DIR/" 2>/dev/null || true
  ok "Backup → $BACKUP_DIR"
}

cmd_update() {
  info "Update = backup + upgrade"
  cmd_backup
  cmd_upgrade
}

cmd_localai() {
  local action="${1:-status}"
  detect_docker; detect_resources; detect_pterodactyl; detect_localai
  case "$action" in
    install)
      install_localai_full
      detect_and_select_models
      ;;
    start)
      if $DOCKER_CAN_RUN && docker ps -a --format '{{.Names}}' | grep -qx local-ai; then
        docker start local-ai && ok "Docker LocalAI started"
      elif [[ -f "${LOCALAI_DIR}/local-ai" ]]; then
        nohup "${LOCALAI_DIR}/local-ai" --address "0.0.0.0:${LOCALAI_PORT}" \
          --models-path "$LOCALAI_MODELS_DIR" > "${LOG_DIR}/localai.log" 2>&1 &
        echo $! > "${LOCALAI_DIR}/localai.pid"
        ok "Binary started"
      else
        warn "Nothing to start — run: bash install.sh --localai-install"
      fi
      ;;
    stop)
      if $DOCKER_CAN_RUN; then
        docker stop local-ai 2>/dev/null && ok "Docker stopped" || true
      fi
      if [[ -f "${LOCALAI_DIR}/localai.pid" ]]; then
        kill "$(cat "${LOCALAI_DIR}/localai.pid")" 2>/dev/null || true
        rm -f "${LOCALAI_DIR}/localai.pid"
        ok "Binary stopped"
      fi
      ;;
    restart)
      cmd_localai stop
      sleep 2
      cmd_localai start
      ;;
    status) cmd_status ;;
    models)
      detect_localai
      curl -sf "${LOCALAI_URL}/v1/models" 2>/dev/null || echo "unreachable"
      echo
      detect_and_select_models
      ;;
    logs)
      if $DOCKER_CAN_RUN; then
        docker logs --tail 50 local-ai 2>/dev/null || true
      fi
      tail -n 50 "${LOG_DIR}/localai.log" 2>/dev/null || true
      ;;
    *)
      echo "Usage: --localai-install|start|stop|restart|status|models|logs"
      ;;
  esac
}

cmd_uninstall() {
  warn "Stops LocalAI container/binary and removes venv. Data kept."
  detect_docker
  if $DOCKER_CAN_RUN; then
    docker stop local-ai 2>/dev/null || true
    docker rm local-ai 2>/dev/null || true
  fi
  if [[ -f "${LOCALAI_DIR}/localai.pid" ]]; then
    kill "$(cat "${LOCALAI_DIR}/localai.pid")" 2>/dev/null || true
  fi
  rm -rf "$VENV_DIR"
  ok "Runtime removed. Project + data preserved."
}

# ---------------------------------------------------------------------------
# Full install
# ---------------------------------------------------------------------------
full_install() {
  banner
  detect_os; detect_resources; detect_python; detect_docker; detect_pterodactyl

  step "1/10 Detecting system"
  info "OS=$OS_ID $OS_VERSION | Arch=$ARCH_NORM | CPU=$CPU_CORES | RAM=${RAM_MB}MB | Disk=${DISK_GB}GB"
  info "GPU=$GPU_INFO | CUDA=$CUDA_AVAILABLE | Docker=$DOCKER_CAN_RUN | Pterodactyl=$IS_PTERODACTYL"
  info "Recommended model for this RAM: $(recommend_model)"

  if [[ -z "$PYTHON" ]]; then
    fail "Python 3 required"
    exit 1
  fi

  install_python_deps
  install_localai_full
  detect_and_select_models
  configure_discord
  configure_tools
  run_health_checks

  echo
  echo -e "${G}${BOLD}══════════════════════════════════════${N}"
  echo -e "${G}${BOLD}  SVM AI READY  ·  v${SVMAI_VERSION}${N}"
  echo -e "${G}${BOLD}══════════════════════════════════════${N}"
  echo
  echo "  Discord   → .env"
  echo "  LocalAI   → ${LOCALAI_URL:-not set}"
  echo "  Database  → ./data"
  echo "  Workspace → ./workspace"
  echo
  if $IS_PTERODACTYL; then
    echo "  Pterodactyl start command:"
    echo "    python bot.py"
    echo "  Make sure LOCALAI_URL points to a reachable LocalAI host."
  else
    echo "  Start:  source .venv/bin/activate && python bot.py"
  fi
  echo "  Doctor: bash install.sh --doctor"
  echo "  LocalAI: bash install.sh --localai-status"
  echo

  if [[ "${NON_INTERACTIVE:-0}" != "1" ]] && ! $IS_PTERODACTYL; then
    echo -n "Start SVM AI now? [Y/n] "
    read -r ans || true
    if [[ -z "${ans:-}" || "$ans" =~ ^[Yy] ]]; then
      start_bot
    fi
  fi
}

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR" "$DATA_DIR" "$WORKSPACE_DIR"

case "${1:-}" in
  --doctor)            cmd_doctor ;;
  --status)            cmd_status ;;
  --repair)            cmd_repair ;;
  --update|--upgrade)  cmd_update ;;
  --backup)            cmd_backup ;;
  --uninstall)         cmd_uninstall ;;
  --configure)         configure_discord; configure_tools ;;
  --localai-install)   cmd_localai install ;;
  --localai-start)     cmd_localai start ;;
  --localai-stop)      cmd_localai stop ;;
  --localai-restart)   cmd_localai restart ;;
  --localai-status)    cmd_localai status ;;
  --localai-models)    cmd_localai models ;;
  --localai-logs)      cmd_localai logs ;;
  --non-interactive)   NON_INTERACTIVE=1; full_install ;;
  --help|-h)
    cat << EOF
SVM AI installer v${SVMAI_VERSION} — Made by AnkitCoder

  (no args)              Full install (VPS auto LocalAI / Ptero-aware)
  --doctor               Full diagnostics
  --status               Runtime + LocalAI status
  --repair               Fix deps, LocalAI, models, dirs
  --upgrade / --update   Git pull or GITHUB_REPO upgrade + repair
  --backup               Backup .env + data + workspace
  --configure            Discord token / admin IDs
  --localai-install      Auto install & configure LocalAI
  --localai-start|stop|restart|status|models|logs
  --non-interactive      No prompts (CI / scripts)
  --uninstall            Remove venv + stop LocalAI

Env overrides:
  GITHUB_REPO=https://github.com/USER/svm-ai.git
  GITHUB_BRANCH=main
  LOCALAI_URL=http://127.0.0.1:8080
  NON_INTERACTIVE=1
EOF
    ;;
  *) full_install ;;
esac
