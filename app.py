import os
import sqlite3
import random
import uuid
import time

from flask import Flask, request, jsonify, send_from_directory, abort, render_template
from werkzeug.utils import secure_filename
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'grabit.db')

MAX_EXPIRY_HOURS = 120  # 5 days

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_name TEXT,
            is_link INTEGER NOT NULL DEFAULT 0,
            url TEXT,
            expires_at REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def generate_code(length=6):
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))


def code_exists(code):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT 1 FROM files WHERE code = ?', (code,)).fetchone()
    conn.close()
    return row is not None


def cleanup_expired():
    """Delete any files (from disk and database) whose expiry time has passed."""
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    expired_rows = conn.execute(
        'SELECT id, stored_name FROM files WHERE expires_at < ? AND is_link = 0', (now,)
    ).fetchall()

    for _id, stored_name in expired_rows:
        if stored_name:
            file_path = os.path.join(UPLOAD_FOLDER, stored_name)
            if os.path.exists(file_path):
                os.remove(file_path)

    conn.execute('DELETE FROM files WHERE expires_at < ?', (now,))
    conn.commit()
    conn.close()


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/how-it-works')
def how_it_works():
    return render_template('how-it-works.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/api/send', methods=['POST'])
def send_file():
    cleanup_expired()

    uploaded_files = request.files.getlist('file')
    uploaded_files = [f for f in uploaded_files if f.filename != '']

    link = request.form.get('link', '').strip()

    if not uploaded_files and not link:
        return jsonify({'error': 'No files or link provided'}), 400

    custom_code = request.form.get('code', '').strip().upper()

    try:
        expiry_hours = float(request.form.get('expiry_hours', 24))
    except ValueError:
        expiry_hours = 24

    expiry_hours = max(1/60, min(expiry_hours, MAX_EXPIRY_HOURS))
    expires_at = time.time() + (expiry_hours * 3600)

    if custom_code:
        if code_exists(custom_code):
            return jsonify({'error': 'This code is already taken'}), 409
        code = custom_code
    else:
        code = generate_code()
        while code_exists(code):
            code = generate_code()

    conn = sqlite3.connect(DB_PATH)

    for uploaded_file in uploaded_files:
        unique_suffix = uuid.uuid4().hex[:8]
        stored_name = f"{code}_{unique_suffix}_{secure_filename(uploaded_file.filename)}"
        save_path = os.path.join(UPLOAD_FOLDER, stored_name)
        uploaded_file.save(save_path)

        conn.execute(
            'INSERT INTO files (code, filename, stored_name, is_link, url, expires_at) '
            'VALUES (?, ?, ?, 0, NULL, ?)',
            (code, uploaded_file.filename, stored_name, expires_at)
        )

    if link:
        conn.execute(
            'INSERT INTO files (code, filename, stored_name, is_link, url, expires_at) '
            'VALUES (?, ?, NULL, 1, ?, ?)',
            (code, link, link, expires_at)
        )

    conn.commit()
    conn.close()

    total_items = len(uploaded_files) + (1 if link else 0)
    return jsonify({'code': code, 'count': total_items})


@app.route('/api/list/<code>')
def list_files(code):
    cleanup_expired()
    code = code.strip().upper()

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        'SELECT id, filename, is_link, url FROM files WHERE code = ?', (code,)
    ).fetchall()
    conn.close()

    if not rows:
        abort(404)

    files = []
    for row in rows:
        item_id, filename, is_link, url = row
        if is_link:
            files.append({'id': item_id, 'type': 'link', 'url': url})
        else:
            files.append({'id': item_id, 'type': 'file', 'filename': filename})

    return jsonify({'files': files})


@app.route('/api/download/<int:file_id>')
def download_file(file_id):
    cleanup_expired()

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        'SELECT filename, stored_name FROM files WHERE id = ? AND is_link = 0', (file_id,)
    ).fetchone()
    conn.close()

    if row is None:
        abort(404)

    original_filename, stored_name = row
    return send_from_directory(
        UPLOAD_FOLDER,
        stored_name,
        as_attachment=True,
        download_name=original_filename
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=True)