# Grabit

A simple file sharing web app. Upload files or a link, get a code, and share it. The receiver enters the code to download.

## Features
- Send multiple files and/or a link with one code
- Auto-generated or custom code
- Expiry time selector (12 hours to 5 days, or custom)
- Receiver can choose which files to download
- Expired files are deleted automatically

## Tech Stack
Python, Flask, SQLite, HTML, CSS, JavaScript

## How to Run
1. Install Flask: `pip install flask`
2. Run: `python app.py`
3. Open `http://127.0.0.1:5000` in your browser