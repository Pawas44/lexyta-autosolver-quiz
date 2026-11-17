# 🎓 Lexyta LMS Auto Quiz Solver & Assignment Notifier 🚀

> **Production-Grade Modular Architecture inspired by modern Agent & Engineering Standards.**

Automation system for **Lexyta LMS** (`https://lms.lexyta.com`).
Designed to run seamlessly on **Android Mobile (Termux)**, **Linux VPS**, **Docker Containers**, or **100% Free 24/7 via GitHub Actions**.

---

## 🌟 Key Capabilities

1. 🔐 **Auto Authentication**:
   - Securely logs into Lexyta LMS with provided credentials (`pawasnishant1327@gmail.com`).
   - Automatically maintains session cookies, JWT authentication token, and CSRF (`X-CSRF-TOKEN`) headers with auto-renewal upon expiration.
2. 📚 **Program & Course Discovery**:
   - Accesses enrolled program (`BCA_IP_2025-2029`).
   - Scans all active semester classes (IDA, OS, Python Programming, SE, COA, PMOB, etc.).
3. 🧠 **AI-Powered Quiz Auto-Solver & Submitter**:
   - Detects any **newly published Quiz**.
   - Initiates attempt (`/api/classes/{id}/student/assignments/{quiz_id}/attempts/start`).
   - Fetches questions, sections, and multiple-choice options (`/api/.../quiz/view`).
   - Sends questions to **Google Gemini AI** (`gemini-3.1-flash-lite`, `gemini-3.8-flash`) with prompt engineering for academic accuracy.
   - Formats answers payload and automatically submits to LMS.
   - Sends confirmation notification to your mobile number.
4. 📢 **Assignment Notifier (`9315135782`)**:
   - When a **New Assignment** (Document/Exam) is posted:
   - Extracts subject name, assignment title, due date, description, and attached file names (e.g. `IDA Assignment 2.pdf`).
   - Dispatches an instant alert directly to **`9315135782`** via WhatsApp / Termux SMS / Push Notification.

---

## 🏗️ Architecture & Project Structure

```text
lexyta-auto-solver/
├── src/
│   ├── client/
│   │   ├── lexyta_api.py       # Full REST API client with CSRF & session handling
│   │   └── exceptions.py       # Typed domain exceptions (LMSAuthError, LMSQuizError)
│   ├── core/
│   │   ├── config.py           # Typed dataclass config loader (JSON + env overrides)
│   │   ├── state.py            # Atomic state persistence for solved quizzes & alerts
│   │   └── logger.py           # Rotating file & clean console logger
│   ├── engine/
│   │   └── scanner.py          # Orchestration engine: diffing, solving & notifying
│   ├── notifiers/
│   │   ├── base.py             # Abstract Base Notifier interface
│   │   ├── dispatcher.py       # Multi-channel notification router
│   │   ├── whatsapp.py         # CallMeBot WhatsApp integration
│   │   ├── termux.py           # Native Android SMS & Push notification
│   │   ├── sms.py              # Fast2SMS Indian SMS gateway
│   │   └── telegram.py         # Telegram bot integration
│   ├── solvers/
│   │   ├── base.py             # Abstract Base Solver interface
│   │   └── gemini_solver.py    # Google Gemini AI solver with model fallback
│   └── cli/
│       └── main.py             # Rich CLI with arguments (--once, --dry-run, --test-ai)
├── config/
│   └── config.json             # Configuration file
├── scripts/
│   ├── run_mobile.sh           # 1-Click Android Termux setup & background runner
│   ├── run_daemon.sh           # Linux/VPS background daemon runner
│   └── run_windows.bat         # 1-Click Windows launch script
├── tests/
│   ├── test_client.py          # API authentication & profile test
│   └── test_solver.py          # Gemini AI solving accuracy test
├── .github/workflows/
│   └── lms_cron.yml            # Free 24/7 Cloud runner via GitHub Actions
├── run.py                      # Root executable entrypoint
├── requirements.txt            # Minimal dependencies (requests only)
├── Dockerfile                  # Container build file
└── docker-compose.yml          # Container orchestration
```

---

## ⚡ Quick Start & Commands

### 1. Verify LMS Login & Account:
```bash
python run.py --test-login
```
*Output: Verifies student profile (`Pawas Pant`), ID, and enrolled program (`BCA_IP_2025-2029`).*

### 2. Verify Gemini AI Quiz Solver:
```bash
python run.py --test-ai
```
*Output: Tests Gemini API with a sample academic question and validates answer accuracy.*

### 3. Run Dry-Run Simulation:
```bash
python run.py --dry-run --once
```
*Output: Scans all subjects and displays what would be solved or alerted without modifying LMS or sending external SMS.*

### 4. Run Live Single Pass (Ideal for Cron):
```bash
python run.py --once
```

### 5. Run Continuous Background Daemon:
```bash
python run.py --interval 15
```

---

## 📱 Running on Android Mobile (Termux)

Because the project is built in pure lightweight Python with zero browser dependencies, it uses minimal battery and memory (~20 MB).

1. Install **Termux** on your Android phone.
2. Run in Termux:
   ```bash
   pkg update -y && pkg install python git -y
   ```
3. Copy or clone this folder into Termux and execute:
   ```bash
   chmod +x scripts/run_mobile.sh
   ./scripts/run_mobile.sh
   ```
   *(Termux automatically activates `termux-wake-lock` so Android does not kill the process when the phone is locked).*

---

## ☁️ Running 100% Free 24/7 via GitHub Actions

No PC or phone needs to stay on:
1. Push this folder to a **Private GitHub repository**.
2. Go to repository **Actions** tab — the included `.github/workflows/lms_cron.yml` is pre-configured to run automatically every **20 minutes** for free!

---

## 💬 9315135782 WhatsApp Notification Setup

To receive WhatsApp alerts via the free CallMeBot gateway:
1. Send WhatsApp message: `I allow callmebot to send me messages` to **`+34 644 44 49 64`**
2. CallMeBot will reply with your free API Key.
3. Put the key in `config/config.json`:
   ```json
   "whatsapp_callmebot": {
     "enabled": true,
     "api_key": "YOUR_API_KEY_HERE"
   }
   ```
4. If running on Termux on the mobile itself (`pkg install termux-api`), native SMS will be dispatched directly from your phone's SIM card without needing any third-party API key!

---

## 🧪 Automated Tests

Run all unit tests:
```bash
python -m unittest discover tests
```
