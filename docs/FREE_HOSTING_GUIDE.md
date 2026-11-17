# 🌐 Free 24/7 Online Cloud Hosting Guide

This guide explains how to host the **Lexyta LMS Multi-User Telegram Server** (`run_server.py`) online 100% free of cost, so the bot remains online 24/7 even when your PC is turned off.

---

## 🚀 Option 1: Render.com (Recommended - 100% Free)

Render provides free hosting for background services and web apps.

1. Create a free account at [Render.com](https://render.com).
2. Click **New +** ➔ **Web Service** (or Background Worker).
3. Connect your GitHub repository:
   `https://github.com/Pawas44/lexyta-autosolver-quiz` (or your private repo).
4. Configure the service:
   - **Name:** `lexyta-lms-bot`
   - **Environment:** `Python 3`
   - **Region:** Singapore / Frankfurt / Oregon
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python run_server.py`
5. Under **Environment Variables**, add:
   - `MASTER_BOT_TOKEN`: `9266694753:AAG3ipGnDEhZQqDNz0MQJd2n2yHRoYrQ9Mk`
6. Click **Create Web Service**! Render will deploy it automatically and keep it running 24/7.

---

## 🚀 Option 2: Koyeb (100% Free Serverless Container)

Koyeb provides 512MB RAM and 2 free micro services.

1. Sign up at [Koyeb.com](https://www.koyeb.com).
2. Click **Create App** ➔ **GitHub**.
3. Select your repository.
4. Set:
   - **Builder:** `Buildpack` or `Dockerfile`
   - **Run Command:** `python run_server.py`
5. Add Environment Variable:
   - `MASTER_BOT_TOKEN`: `9266694753:AAG3ipGnDEhZQqDNz0MQJd2n2yHRoYrQ9Mk`
6. Click **Deploy**. Your bot will be live in 60 seconds!

---

## 🚀 Option 3: Oracle Cloud Free Tier (Most Powerful - VPS 24/7 Free Forever)

Oracle Cloud gives you an **Always Free VPS** with:
- **4 ARM OCPUs**
- **24 GB RAM**
- **200 GB Storage**

1. Sign up for [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/).
2. Create an **Ubuntu 24.04** VM instance.
3. SSH into your server:
   ```bash
   ssh ubuntu@YOUR_SERVER_IP
   ```
4. Clone the repo and start with systemd:
   ```bash
   git clone https://github.com/Pawas44/lexyta-autosolver-quiz.git
   cd lexyta-autosolver-quiz
   pip install -r requirements.txt
   nohup python3 run_server.py > logs/server.log 2>&1 &
   ```
The bot will run forever without any sleep or idle timeouts.

---

## 🚀 Option 4: Android Phone (Termux - Free in your Pocket)

If you have an old Android phone:
1. Install **Termux** from F-Droid.
2. Run:
   ```bash
   pkg update -y && pkg install python git -y
   git clone https://github.com/Pawas44/lexyta-autosolver-quiz.git
   cd lexyta-autosolver-quiz
   pip install -r requirements.txt
   termux-wake-lock
   python run_server.py
   ```
Your phone will host the bot 24/7 while charging on Wi-Fi with ~20MB RAM usage.
