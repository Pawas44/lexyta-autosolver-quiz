# 🎓 Lexyta LMS Auto Quiz Solver & Informer Bot

> 24/7 Telegram bot that **auto-solves quizzes**, **alerts on new assignments**, **downloads lecture notes**, and **sends marks** — all from your Lexyta LMS account. Works for **any course** (BCA, BBA, B.Tech, MCA, etc.).

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **AI Quiz Auto-Solver** | Detects new quizzes → Solves with Google Gemini AI → Submits with human-like timing |
| ⏱️ **Stealth Human Pacing** | 20 min quiz → ~13 min, 15 min → ~9 min. Teachers see natural completion times |
| 📢 **Assignment Alerts** | Instant Telegram notification when a new assignment is posted with due date |
| 📊 **Marks Notifier** | Sends released scores/grades directly to your Telegram chat |
| 📂 **Notes & PPT Downloader** | Download lecture notes, PPTs, practicals, and outlines on-demand |
| 👥 **Multi-User Support** | Multiple students can connect their own LMS accounts via one bot |
| 🔒 **Whitelist Access Control** | Only authorized chat IDs (GitHub whitelist) can use the bot |
| ☁️ **Cloud State Persistence** | Quiz/assignment state synced to GitHub — survives server restarts |
| 🔄 **24/7 Background Scanning** | Scans LMS every 5 minutes automatically |
| 🏥 **Self-Healing Keep-Alive** | Built-in self-ping prevents free hosting from sleeping |

---

## 📋 Bot Commands

After linking your account with `/start`, use these commands:

| Command | What It Does |
|---------|--------------|
| `/start` | Link your Lexyta LMS account (interactive setup) |
| `/quiz` | Check how many quizzes are pending |
| `/solve` | Solve & submit all pending quizzes with AI right now |
| `/assignments` | View open assignments with due dates |
| `/notes` | Browse & download lecture notes, PPTs by subject |
| `/getfile_N` | Download a specific file (e.g. `/getfile_1`) |
| `/getall` | Download all files of a subject at once |
| `/marks` | View released marks & results |
| `/status` | Check your account & monitoring status |
| `/scan` | Trigger an instant LMS scan |
| `/pause` | Pause automatic monitoring |
| `/resume` | Resume automatic monitoring |
| `/relink` | Update your LMS credentials |
| `/unlink` | Disconnect your LMS account |
| `/id` | Show your Telegram chat ID (for whitelist) |
| `/help` | List all commands |

---

## 🚀 Self-Hosting Guide (Step by Step)

### Prerequisites

- A **GitHub account** (free)
- A **Telegram account**
- A **Render account** (free) — [render.com](https://render.com)
- A **Google Gemini API key** (free) — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Give your bot a **name** (e.g. `My Lexyta Bot`)
4. Give it a **username** (e.g. `my_lexyta_bot`)
5. BotFather will send you a **Bot Token** like:
   ```
   7123456789:AAH_your_secret_token_here
   ```
6. **Copy this token** — you'll need it in Step 4

---

### Step 2: Get Your Gemini API Key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click **"Create API Key"**
3. Copy the key (starts with `AIza...`)
4. You'll enter this during bot setup (`/start`) — or set it as a default in Render env vars

---

### Step 3: Fork & Deploy on Render

#### 3a. Fork This Repository
1. Click the **Fork** button on this GitHub repo (top-right)
2. This creates your own copy at `github.com/YOUR_USERNAME/lexyta-autosolver-quiz`

#### 3b. Set Up Whitelist
1. In your forked repo, open **`allowed_chats.txt`**
2. Add your Telegram Chat ID (one per line)
   - Don't know your Chat ID? Send `/id` to any existing Telegram bot, or search for `@userinfobot` on Telegram
3. Commit the file

#### 3c. Deploy on Render (Free)
1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**
2. Connect your GitHub account and select your forked repo
3. Configure:
   | Setting | Value |
   |---------|-------|
   | **Name** | `lexyta-bot` (or anything) |
   | **Region** | Any (closest to India = Singapore) |
   | **Branch** | `main` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `python run_server.py` |
   | **Plan** | **Free** |

4. **Add Environment Variables** (click "Add Environment Variable"):

   | Key | Value | Required |
   |-----|-------|----------|
   | `MASTER_BOT_TOKEN` | Your Telegram bot token from Step 1 | ✅ Yes |
   | `GITHUB_TOKEN` | GitHub Personal Access Token ([create here](https://github.com/settings/tokens/new?scopes=repo)) | Optional (for state persistence) |
   | `DEFAULT_GEMINI_KEY` | Your Gemini API key from Step 2 | Optional (users can set their own during /start) |

5. Click **Create Web Service** → Wait for deploy (2-3 minutes)

---

### Step 4: Start Using the Bot

1. Open Telegram and search for your bot's username
2. Send `/start`
3. Follow the interactive setup:
   - **Step 1/4**: Enter your Lexyta LMS email
   - **Step 2/4**: Enter your Lexyta LMS password
   - **Step 3/4**: Enter your Gemini API key (or type `default` to use the system key)
   - **Step 4/4**: Enter semester filter (type `auto` for automatic detection)
4. Done! The bot will now:
   - Scan your LMS every 5 minutes
   - Auto-solve new quizzes
   - Alert you on new assignments
   - Send marks when released

---

### Step 5: Keep It Alive 24/7 (Recommended)

Render's free tier sleeps after 15 minutes of no traffic. The bot has a **built-in self-pinger**, but for extra reliability:

1. Go to [UptimeRobot](https://uptimerobot.com) (free account)
2. Add a new **HTTP(s) Monitor**:
   - **URL**: `https://your-app-name.onrender.com`
   - **Interval**: 5 minutes
3. This keeps your bot alive 24/7 for free

---

## 🏗️ Architecture

```
lexyta-autosolver/
├── run_server.py              # Main server entry point (HTTP + Bot + Scanner)
├── src/
│   ├── bot/
│   │   └── telegram_server.py # Telegram bot with interactive onboarding & all commands
│   ├── client/
│   │   ├── lexyta_api.py      # Reverse-engineered Lexyta LMS REST API client
│   │   └── exceptions.py      # Custom exception classes
│   ├── core/
│   │   ├── access_control.py  # GitHub whitelist-based access control
│   │   ├── config.py          # Configuration loader
│   │   ├── github_sync.py     # Cloud state persistence via GitHub API
│   │   ├── user_manager.py    # Multi-user credential & state manager
│   │   ├── state.py           # Local state persistence
│   │   └── logger.py          # Logging setup
│   ├── engine/
│   │   ├── scanner.py         # Single-user LMS scanner with auto-semester detection
│   │   └── multi_scanner.py   # Multi-user scanner with access control
│   ├── solvers/
│   │   ├── gemini_solver.py   # Google Gemini AI quiz solver (Chain-of-Thought, 4-model fallback)
│   │   ├── human_pacer.py     # Stealth human-like quiz completion timing
│   │   └── base.py            # Abstract solver interface
│   └── notifiers/
│       ├── telegram.py        # Telegram message formatting
│       ├── dispatcher.py      # Multi-channel notification router
│       └── ...                # WhatsApp, SMS, Termux notifiers
├── tampermonkey/               # Browser scripts for in-class quiz solving
│   ├── lexyta-shield-pro.user.js    # Proctoring bypass (14 defense layers)
│   └── lexyta-study-helper.user.js  # In-browser AI quiz answer highlighter
├── chrome-extension/           # Chrome extension (alternative to Tampermonkey)
├── allowed_chats.txt           # Authorized Telegram chat IDs (whitelist)
├── render.yaml                 # Render deployment config
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker support
└── tests/                      # Unit tests
```

---

## 🧠 How the AI Solver Works

```
Quiz Detected → Start Attempt → Fetch Questions → Gemini AI (Chain-of-Thought)
     ↓                                                    ↓
  Human Pacing ←──── Wait for realistic duration ←──── Answers Ready
     ↓
  Submit to LMS → Notify Student on Telegram
```

1. **Detection**: Background scanner finds new quizzes every 5 minutes
2. **Attempt**: Starts a quiz attempt via LMS API
3. **AI Solving**: Sends questions to Google Gemini with academic Chain-of-Thought prompting
4. **Model Fallback**: Tries 4 Gemini models in sequence if one fails
5. **Human Pacing**: Waits a realistic amount of time before submitting:
   - 20 min quiz → submits at ~13 min
   - 15 min quiz → submits at ~9 min
   - Always submits 60 seconds before deadline (safety cap)
6. **Submission**: Submits answers to LMS and notifies the student

---

## 👥 Adding New Users

1. The new user sends `/id` to the bot to get their Telegram Chat ID
2. Admin adds their Chat ID to `allowed_chats.txt` in the GitHub repo (one ID per line)
3. The user sends `/start` to the bot and completes the setup
4. Done — the bot will now monitor their LMS account too

---

## ⚙️ Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MASTER_BOT_TOKEN` | Telegram Bot API token | ✅ |
| `GITHUB_TOKEN` | GitHub PAT for cloud state sync | ❌ |
| `DEFAULT_GEMINI_KEY` | Default Gemini API key for all users | ❌ |
| `CHECK_INTERVAL_MINUTES` | Scan interval in minutes (default: 5) | ❌ |
| `PORT` | HTTP server port (default: 10000) | ❌ |

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

---

## 🔒 Security Notes

- **Never commit your bot token** to the repository. Always use environment variables.
- **Never commit personal credentials** (email/password). Users enter them via Telegram `/start`.
- The `config/config.json` file is in `.gitignore` — it should never be pushed to public repos.
- User passwords are stored locally in `data/users.json` on the server. On Render free tier, this file is ephemeral (lost on restart). Use `GITHUB_TOKEN` for persistent state.
- The whitelist (`allowed_chats.txt`) controls who can use the bot.

---

## 📄 License

MIT License — Use freely, modify, and deploy. No warranty provided.
