# 🚀 Fiber Anomaly Detection Bot (IXC API)

An automated Python script designed to monitor fiber optic signal anomalies (RX/TX) from the IXC ISP management system and synchronize the data with a Google Sheets dashboard. 

## 📌 Overview

This bot intelligently scans the network for OLT clients with critical optical signals. Before adding a client to the spreadsheet, it checks the IXC database for active Support Tickets (Ordens de Serviço). It avoids redundant dispatching by ignoring clients who already have ongoing technical support, while flagging specific ticket subjects with observations.

## ✨ Key Features

- **Optical Signal Monitoring:** Automatically flags clients with `RX >= -16` or `RX <= -26`, and `TX < -27`.
- **Smart OS Filtering:** 
  - Skips clients with active support tickets to prevent double-dispatching.
  - Whitelists specific OS subjects (e.g., 67, 118, 119, 18, 101, 127) and adds them to the sheet with an observation.
- **Google Sheets Integration:** Syncs data in real-time, removing normalized clients and appending new anomalies.
- **High Performance:** Uses `ThreadPoolExecutor` for concurrent API requests, significantly reducing processing time.

## ⚙️ Requirements

- Python 3.8+
- Google Cloud Service Account Credentials (`.json`)
- IXC API Token

### Python Libraries
```bash
pip install requests gspread