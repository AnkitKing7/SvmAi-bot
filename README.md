# SVM AI v1.1.0

**Ultimate Autonomous Discord AI Agent**  
**Made by AnkitCoder**

SVM AI is a production-ready Discord bot that acts as a **full autonomous agent** — not a simple chatbot. It combines conversation, deep research, multi-file coding, GitHub analysis, SEO auditing, debugging, vision, and image generation, with **LocalAI** as the primary AI engine.

---

## Download (complete package)

| File | Description |
|------|-------------|
| **`SVM-AI-v1.1.0.zip`** | Full release — all source files ready to upload |

**ZIP contents:**

```
SVM-AI-v1.1.0.zip
├── bot.py              # Main application (autonomous agent)
├── install.sh          # Auto installer + LocalAI setup (VPS / Pterodactyl)
├── requirements.txt    # Python dependencies
├── .env.example        # Config template
├── README.md           # This file
└── Dockerfile          # Optional container build
```

### Quick start from ZIP

```bash
# 1. Upload & extract on VPS or Pterodactyl
unzip SVM-AI-v1.1.0.zip -d svm-ai
cd svm-ai

# 2. Run installer (auto LocalAI on VPS)
sudo bash install.sh

# 3. Start bot
source .venv/bin/activate
python bot.py
```

Pterodactyl: upload ZIP → extract → `bash install.sh` → panel start command `python bot.py`.

---

## Features

| Capability | Description |
|---|---|
| **Universal `/ask`** | Auto-routes to the right tool (chat, code, research, vision…) |
| **IQ200** | Highest reasoning mode with progress indicators |
| **Deep research** | Multi-query search, page reading, cross-checking, citations |
| **Coding agent** | Multi-file project generation, test, repair loop, ZIP export |
| **GitHub agent** | Public repo analysis (structure, security, architecture) |
| **SEO agent** | URL audit or keyword/topic strategy |
| **Debug / Logs** | Traceback & error root-cause analysis |
| **Vision** | Image understanding via LocalAI vision models |
| **Image gen** | LocalAI or external image providers |
| **URL tools** | Fetch, summarize, verify (with SSRF protection) |
| **Projects** | Per-user isolated workspaces, list / zip / delete |
| **Memory** | SQLite conversation + project context |
| **Security** | Path isolation, secret masking, rate limits, admin gates |

---

## Architecture

```
Discord  ←→  bot.py (single-file agent)
                ├── LocalAI client (primary)
                ├── Search providers (Brave / Tavily / Serper / Bing)
                ├── Web / URL tools (SSRF-safe)
                ├── Coding agent + workspace + tester
                ├── GitHub analyzer
                ├── SEO analyzer
                └── SQLite (users, sessions, projects, usage)
```

Everything lives in **`bot.py`** for easy deployment on VPS, Pterodactyl, or Docker.

---

## Requirements

- Python 3.10+
- Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- LocalAI instance (auto-installed on VPS when possible, or external URL)
- Optional: search API key, image API key

---

## Installation

### Option A — ZIP download (recommended)

1. Download **`SVM-AI-v1.1.0.zip`**
2. Upload to VPS / Pterodactyl
3. Extract and run installer:

```bash
unzip SVM-AI-v1.1.0.zip -d svm-ai && cd svm-ai
sudo bash install.sh
source .venv/bin/activate
python bot.py
```

### Option B — Git clone + upgrade

```bash
git clone https://github.com/YOUR_USER/svm-ai.git
cd svm-ai
bash install.sh

# Later updates:
bash install.sh --upgrade
```

Or without local git history:

```bash
export GITHUB_REPO=https://github.com/YOUR_USER/svm-ai.git
export GITHUB_BRANCH=main
bash install.sh --upgrade
```

`.env`, `data/`, `workspace/` are preserved on upgrade.

---

## VPS — full automatic LocalAI

On a normal VPS the installer:

1. Detects OS, CPU, RAM, GPU, CUDA, Docker  
2. Installs Docker if missing (root)  
3. Runs **LocalAI All-in-One**:
   - CPU → `localai/localai:latest-aio-cpu`
   - NVIDIA → `latest-aio-gpu-nvidia-cuda-12` / `cuda-13`
4. Waits for `/v1/models`  
5. Writes model names into `.env`  
6. Tries a small gallery model if none exist (RAM-based)

```bash
sudo bash install.sh
sudo bash install.sh --localai-install
bash install.sh --localai-status
bash install.sh --localai-models
bash install.sh --localai-logs
```

---

## Pterodactyl

Eggs usually **cannot** run Docker-in-Docker. Installer detects Pterodactyl and:

1. Asks for an **external LocalAI URL** (host VPS / other server), or  
2. Tries official LocalAI binary install (no Docker), or  
3. Lets you set `LOCALAI_URL` later in `.env`

**Recommended layout:**

| Layer | What runs |
|--------|-----------|
| Host / separate VPS | LocalAI Docker AIO on port `8080` |
| Pterodactyl egg | SVM AI bot only |

```bash
# Inside egg after ZIP upload + extract:
bash install.sh
# When prompted: http://YOUR_HOST_IP:8080

# Panel → Startup command:
python bot.py
```

`.env` example:

```env
LOCALAI_URL=http://203.0.113.10:8080
DISCORD_TOKEN=your_token_here
ADMIN_IDS=123456789012345678
```

---

## Docker (bot only)

```bash
docker build -t svm-ai .
docker run -d --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/workspace:/app/workspace \
  --name svm-ai \
  svm-ai
```

---

## Configuration

Installer copies `.env.example` → `.env` automatically.

| Variable | Purpose |
|---|---|
| `DISCORD_TOKEN` | Bot token (**required**) |
| `ADMIN_IDS` | Comma-separated Discord user IDs |
| `PREFIX` | Prefix commands (default `!`) |
| `LOCALAI_URL` | Default `http://127.0.0.1:8080` |
| `LOCALAI_MODEL` / `LOCALAI_*_MODEL` | Models per role (auto-filled by installer) |
| `SEARCH_PROVIDER` | `brave` / `tavily` / `serper` / `bing` / `custom` |
| `SEARCH_API_KEY` | Provider API key |
| `IMAGE_PROVIDER` / `IMAGE_API_*` | Optional external image backend |
| `WORKSPACE_DIR` / `DATA_DIR` / `LOG_DIR` | Paths |
| `MAX_REPAIR_LOOPS` | Coding repair attempts (default `5`) |
| `RATE_LIMIT_ENABLED` / `USER_COOLDOWN` | Rate limiting |

---

## Commands (Discord)

Slash and prefix both work.

| Command | Description |
|---|---|
| `/ask` `!ask` | Universal agent (auto tool routing) |
| `/iq200` `!iq200` | Max reasoning |
| `/deep` `!deep` | Deep multi-source research |
| `/research` `!research` | Web research + synthesis |
| `/code` `!code` | Multi-file coding agent |
| `/github` `!github` | Analyze public GitHub repo |
| `/seo` `!seo` | SEO audit / keywords |
| `/debug` `!debug` | Error / traceback analysis |
| `/url` `!url` | Fetch & summarize URL |
| `/image` `!image` | Generate image |
| `/vision` `!vision` | Analyze attached image |
| `/project` `!project` | list / zip / delete projects |
| `/status` `!status` | Health dashboard |
| `/models` `!models` | LocalAI models |
| `/help` `!help` | Help |

---

## Installer commands

```bash
bash install.sh                 # Full install (VPS auto-LocalAI / Ptero-aware)
bash install.sh --doctor        # Full diagnostics
bash install.sh --status        # Runtime + LocalAI status
bash install.sh --repair        # Fix deps / LocalAI / models / dirs
bash install.sh --upgrade       # GitHub / git pull + repair (alias: --update)
bash install.sh --backup        # Backup .env + data + workspace
bash install.sh --configure     # Discord token / admin IDs
bash install.sh --localai-install
bash install.sh --localai-start|stop|restart|status|models|logs
bash install.sh --non-interactive
bash install.sh --uninstall
```

Env overrides:

```bash
export GITHUB_REPO=https://github.com/USER/svm-ai.git
export GITHUB_BRANCH=main
export LOCALAI_URL=http://127.0.0.1:8080
export NON_INTERACTIVE=1
```

---

## LocalAI notes

- **Primary engine** — bot does not silently switch to unknown cloud AI  
- Optional `FALLBACK_AI_URL` / `FALLBACK_AI_KEY` only if LocalAI is fully down and you configured them  
- Models discovered live from `/v1/models`  
- Image gen uses LocalAI `/v1/images/generations` when available  

---

## Security

- Per-user workspace isolation (`workspace/<user_id>/<project_id>/`)  
- Path traversal & zip-slip protection  
- SSRF blocking (private IPs / cloud metadata)  
- Secret masking in logs and outputs  
- Rate limiting (admins can bypass)  
- No unrestricted shell for normal users  

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Missing `DISCORD_TOKEN` | `.env` or `bash install.sh --configure` |
| LocalAI unreachable | `bash install.sh --localai-status` then `--localai-start` |
| No models | Open `http://IP:8080` → Models, or `docker exec -it local-ai local-ai models install tinyllama-chat` |
| Search does nothing | Set `SEARCH_PROVIDER` + `SEARCH_API_KEY` |
| Slash commands missing | Re-invite bot with `applications.commands` scope; wait a few minutes |
| Pterodactyl | External `LOCALAI_URL`; start with `python bot.py` |

```bash
bash install.sh --doctor
tail -f logs/svm_ai.log
bash install.sh --localai-logs
```

---

## File checklist (release)

| File | Required |
|------|----------|
| `bot.py` | Yes — main app |
| `install.sh` | Yes — installer |
| `requirements.txt` | Yes |
| `.env.example` | Yes |
| `README.md` | Yes |
| `Dockerfile` | Optional |
| `SVM-AI-v1.1.0.zip` | Full download package |

---

## License & credits

**Made by AnkitCoder**  
Primary AI engine: [LocalAI](https://localai.io)  
Built for **VPS · Pterodactyl · Docker**
