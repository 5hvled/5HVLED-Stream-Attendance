from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'attendance.db'

def read_text_setting(filename, default):
    try:
        value = (BASE_DIR / filename).read_text(encoding='utf-8-sig').strip()
        return value or default
    except Exception:
        return default

def brand_settings():
    brand_name = read_text_setting('channel_name.txt', 'My Stream')
    twitch_handle = read_text_setting('channel_handle.txt', 'streamer').lstrip('@')
    return (brand_name, twitch_handle)
app = Flask(__name__)
app.secret_key = 'stream-attendance-local-secret'
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.after_request
def disable_browser_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.context_processor
def inject_brand_settings():
    brand_name, twitch_handle = brand_settings()
    return {'brand_name': brand_name, 'twitch_handle': twitch_handle}

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    conn = db()
    conn.executescript("\n    CREATE TABLE IF NOT EXISTS viewers (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        twitch_id TEXT UNIQUE,\n        username TEXT NOT NULL UNIQUE COLLATE NOCASE,\n        display_name TEXT,\n        tracked INTEGER NOT NULL DEFAULT 1,\n        present_adjustment INTEGER NOT NULL DEFAULT 0,\n        absence_adjustment INTEGER NOT NULL DEFAULT 0,\n        notes TEXT NOT NULL DEFAULT '',\n        created_at TEXT NOT NULL\n    );\n\n    CREATE TABLE IF NOT EXISTS streams (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        name TEXT NOT NULL,\n        started_at TEXT NOT NULL,\n        ended_at TEXT,\n        is_open INTEGER NOT NULL DEFAULT 1\n    );\n\n    CREATE TABLE IF NOT EXISTS attendance (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        stream_id INTEGER NOT NULL,\n        viewer_id INTEGER NOT NULL,\n        status TEXT NOT NULL CHECK(status IN ('present','absent')),\n        source TEXT NOT NULL DEFAULT 'manual',\n        updated_at TEXT NOT NULL,\n        UNIQUE(stream_id, viewer_id),\n        FOREIGN KEY(stream_id) REFERENCES streams(id) ON DELETE CASCADE,\n        FOREIGN KEY(viewer_id) REFERENCES viewers(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS punishments (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        viewer_id INTEGER NOT NULL,\n        absence_threshold INTEGER NOT NULL,\n        punished_at TEXT NOT NULL,\n        note TEXT NOT NULL DEFAULT '',\n        FOREIGN KEY(viewer_id) REFERENCES viewers(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS audit_log (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        created_at TEXT NOT NULL,\n        action TEXT NOT NULL,\n        viewer_id INTEGER,\n        stream_id INTEGER,\n        details TEXT NOT NULL DEFAULT ''\n    );\n    ")
    conn.commit()
    conn.close()

def audit(conn, action, viewer_id=None, stream_id=None, details=''):
    conn.execute('INSERT INTO audit_log(created_at, action, viewer_id, stream_id, details) VALUES (?,?,?,?,?)', (now(), action, viewer_id, stream_id, details))

def get_open_stream(conn):
    return conn.execute('SELECT * FROM streams WHERE is_open=1 ORDER BY id DESC LIMIT 1').fetchone()

def get_punishment_state(conn, viewer_id):
    viewer = conn.execute('SELECT absence_adjustment FROM viewers WHERE id=?', (viewer_id,)).fetchone()
    if not viewer:
        return {'absent': 0, 'punishment_count': 0, 'next_threshold': 5, 'eligible': False}
    raw_absent = conn.execute("SELECT COUNT(*) FROM attendance WHERE viewer_id=? AND status='absent'", (viewer_id,)).fetchone()[0]
    absent = max(0, raw_absent + viewer['absence_adjustment'])
    punishment_count = conn.execute('SELECT COUNT(*) FROM punishments WHERE viewer_id=?', (viewer_id,)).fetchone()[0]
    next_threshold = (punishment_count + 1) * 5
    return {'absent': absent, 'punishment_count': punishment_count, 'next_threshold': next_threshold, 'eligible': absent >= next_threshold}

def close_stream_records(conn, stream_id, source='auto-close'):
    stream = conn.execute('SELECT * FROM streams WHERE id=?', (stream_id,)).fetchone()
    if not stream:
        return None
    if not stream['is_open']:
        return {'stream': stream, 'new_absences': 0, 'already_closed': True}
    new_absences = 0
    tracked = conn.execute('SELECT id FROM viewers WHERE tracked=1').fetchall()
    for row in tracked:
        exists = conn.execute('SELECT 1 FROM attendance WHERE stream_id=? AND viewer_id=?', (stream_id, row['id'])).fetchone()
        if not exists:
            conn.execute("\n                INSERT INTO attendance(stream_id, viewer_id, status, source, updated_at)\n                VALUES (?,?,'absent',?,?)\n            ", (stream_id, row['id'], source, now()))
            new_absences += 1
    conn.execute('UPDATE streams SET is_open=0, ended_at=? WHERE id=?', (now(), stream_id))
    audit(conn, 'stream_closed', stream_id=stream_id, details=f'new_absences={new_absences}')
    return {'stream': stream, 'new_absences': new_absences, 'already_closed': False}

def viewer_stats(conn, viewer_id):
    row = conn.execute("\n        SELECT\n            v.*,\n            SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS raw_present,\n            SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS raw_absent,\n            COUNT(a.id) AS recorded_streams\n        FROM viewers v\n        LEFT JOIN attendance a ON a.viewer_id=v.id\n        WHERE v.id=?\n        GROUP BY v.id\n    ", (viewer_id,)).fetchone()
    if not row:
        return None
    raw_present = row['raw_present'] or 0
    raw_absent = row['raw_absent'] or 0
    present = max(0, raw_present + row['present_adjustment'])
    absent = max(0, raw_absent + row['absence_adjustment'])
    total = present + absent
    rate = round(present / total * 100, 1) if total else 0.0
    punishment_count = conn.execute('SELECT COUNT(*) FROM punishments WHERE viewer_id=?', (viewer_id,)).fetchone()[0]
    next_threshold = (punishment_count + 1) * 5
    eligible = absent >= next_threshold
    return {**dict(row), 'raw_present': raw_present, 'raw_absent': raw_absent, 'present': present, 'absent': absent, 'total': total, 'rate': rate, 'punishment_count': punishment_count, 'next_threshold': next_threshold, 'eligible': eligible}

@app.route('/')
def dashboard():
    conn = db()
    open_stream = get_open_stream(conn)
    viewer_ids = [r['id'] for r in conn.execute('SELECT id FROM viewers ORDER BY username COLLATE NOCASE').fetchall()]
    viewers = [viewer_stats(conn, vid) for vid in viewer_ids]
    total_viewers = len(viewers)
    tracked_viewers = sum((1 for v in viewers if v['tracked']))
    danger = sorted([v for v in viewers if v['tracked'] and (not v['eligible']) and (v['absent'] > 0)], key=lambda x: (x['next_threshold'] - x['absent'], -x['absent']))[:8]
    detention = sorted([v for v in viewers if v['tracked'] and v['eligible']], key=lambda x: (-x['absent'], x['username'].lower()))
    recent_streams = conn.execute("\n        SELECT s.*,\n               SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS present_count,\n               SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent_count\n        FROM streams s\n        LEFT JOIN attendance a ON a.stream_id=s.id\n        GROUP BY s.id\n        ORDER BY s.id DESC\n        LIMIT 8\n    ").fetchall()
    current_present = 0
    if open_stream:
        current_present = conn.execute("SELECT COUNT(*) FROM attendance WHERE stream_id=? AND status='present'", (open_stream['id'],)).fetchone()[0]
    conn.close()
    return render_template('dashboard.html', open_stream=open_stream, current_present=current_present, total_viewers=total_viewers, tracked_viewers=tracked_viewers, danger=danger, detention=detention, recent_streams=recent_streams)

@app.route('/viewers')
def viewers():
    q = request.args.get('q', '').strip()
    conn = db()
    if q:
        ids = [r['id'] for r in conn.execute('SELECT id FROM viewers WHERE username LIKE ? OR display_name LIKE ? ORDER BY username COLLATE NOCASE', (f'%{q}%', f'%{q}%')).fetchall()]
    else:
        ids = [r['id'] for r in conn.execute('SELECT id FROM viewers ORDER BY username COLLATE NOCASE').fetchall()]
    rows = [viewer_stats(conn, vid) for vid in ids]
    conn.close()
    return render_template('viewers.html', viewers=rows, q=q)

@app.route('/viewer/<int:viewer_id>')
def viewer_detail(viewer_id):
    conn = db()
    v = viewer_stats(conn, viewer_id)
    if not v:
        conn.close()
        return ('Viewer not found', 404)
    history = conn.execute('\n        SELECT a.*, s.name, s.started_at\n        FROM attendance a\n        JOIN streams s ON s.id=a.stream_id\n        WHERE a.viewer_id=?\n        ORDER BY s.id DESC\n    ', (viewer_id,)).fetchall()
    punishments = conn.execute('\n        SELECT * FROM punishments\n        WHERE viewer_id=?\n        ORDER BY id DESC\n    ', (viewer_id,)).fetchall()
    conn.close()
    return render_template('viewer.html', viewer=v, history=history, punishments=punishments)

@app.post('/viewers/add')
def add_viewer():
    username = request.form.get('username', '').strip().lstrip('@')
    display_name = request.form.get('display_name', '').strip()
    if not username:
        flash('Username is required.')
        return redirect(url_for('viewers'))
    conn = db()
    try:
        cur = conn.execute('INSERT INTO viewers(username, display_name, created_at) VALUES (?,?,?)', (username, display_name or username, now()))
        audit(conn, 'viewer_added', cur.lastrowid, details=username)
        conn.commit()
        flash(f'Added @{username}.')
    except sqlite3.IntegrityError:
        flash(f'@{username} already exists.')
    finally:
        conn.close()
    return redirect(url_for('viewers'))

@app.post('/viewer/<int:viewer_id>/edit')
def edit_viewer(viewer_id):
    username = request.form.get('username', '').strip().lstrip('@')
    display_name = request.form.get('display_name', '').strip()
    twitch_id = request.form.get('twitch_id', '').strip() or None
    notes = request.form.get('notes', '').strip()
    tracked = 1 if request.form.get('tracked') == 'on' else 0
    conn = db()
    old = conn.execute('SELECT * FROM viewers WHERE id=?', (viewer_id,)).fetchone()
    if not old:
        conn.close()
        return ('Viewer not found', 404)
    try:
        conn.execute('\n            UPDATE viewers\n            SET username=?, display_name=?, twitch_id=?, notes=?, tracked=?\n            WHERE id=?\n        ', (username, display_name or username, twitch_id, notes, tracked, viewer_id))
        audit(conn, 'viewer_edited', viewer_id, details=f'username={username}, tracked={tracked}')
        conn.commit()
        flash('Viewer updated.')
    except sqlite3.IntegrityError as e:
        flash(f'Could not update viewer: {e}')
    finally:
        conn.close()
    return redirect(url_for('viewer_detail', viewer_id=viewer_id))

@app.post('/viewer/<int:viewer_id>/adjust')
def adjust_viewer(viewer_id):
    field = request.form.get('field')
    amount = int(request.form.get('amount', '0'))
    if field not in ('present', 'absent') or amount not in (-1, 1):
        return ('Invalid adjustment', 400)
    column = 'present_adjustment' if field == 'present' else 'absence_adjustment'
    conn = db()
    conn.execute(f'UPDATE viewers SET {column}={column}+? WHERE id=?', (amount, viewer_id))
    audit(conn, f'{field}_adjusted', viewer_id, details=f'{amount:+d}')
    conn.commit()
    conn.close()
    return redirect(url_for('viewer_detail', viewer_id=viewer_id))

@app.post('/viewer/<int:viewer_id>/reset/<kind>')
def reset_viewer(viewer_id, kind):
    conn = db()
    if kind == 'absences':
        raw_absent = conn.execute("SELECT COUNT(*) FROM attendance WHERE viewer_id=? AND status='absent'", (viewer_id,)).fetchone()[0]
        conn.execute('UPDATE viewers SET absence_adjustment=? WHERE id=?', (-raw_absent, viewer_id))
        audit(conn, 'absences_reset', viewer_id, details=f'raw_absent={raw_absent}')
        flash('Absence counter reset to 0. History was preserved.')
    elif kind == 'presents':
        raw_present = conn.execute("SELECT COUNT(*) FROM attendance WHERE viewer_id=? AND status='present'", (viewer_id,)).fetchone()[0]
        conn.execute('UPDATE viewers SET present_adjustment=? WHERE id=?', (-raw_present, viewer_id))
        audit(conn, 'presents_reset', viewer_id, details=f'raw_present={raw_present}')
        flash('Present counter reset to 0. History was preserved.')
    elif kind == 'punishments':
        conn.execute('DELETE FROM punishments WHERE viewer_id=?', (viewer_id,))
        audit(conn, 'punishments_reset', viewer_id)
        flash('Punishment history reset.')
    elif kind == 'all':
        raw_absent = conn.execute("SELECT COUNT(*) FROM attendance WHERE viewer_id=? AND status='absent'", (viewer_id,)).fetchone()[0]
        raw_present = conn.execute("SELECT COUNT(*) FROM attendance WHERE viewer_id=? AND status='present'", (viewer_id,)).fetchone()[0]
        conn.execute('UPDATE viewers SET absence_adjustment=?, present_adjustment=? WHERE id=?', (-raw_absent, -raw_present, viewer_id))
        conn.execute('DELETE FROM punishments WHERE viewer_id=?', (viewer_id,))
        audit(conn, 'all_counters_reset', viewer_id)
        flash('All counters reset. Stream history was preserved.')
    else:
        conn.close()
        return ('Invalid reset', 400)
    conn.commit()
    conn.close()
    return redirect(url_for('viewer_detail', viewer_id=viewer_id))

@app.post('/viewer/<int:viewer_id>/punish')
def punish_viewer(viewer_id):
    conn = db()
    v = viewer_stats(conn, viewer_id)
    if not v:
        conn.close()
        return ('Viewer not found', 404)
    threshold = v['next_threshold']
    conn.execute('INSERT INTO punishments(viewer_id, absence_threshold, punished_at, note) VALUES (?,?,?,?)', (viewer_id, threshold, now(), request.form.get('note', '').strip()))
    audit(conn, 'punishment_recorded', viewer_id, details=f'threshold={threshold}')
    conn.commit()
    conn.close()
    flash(f"Punishment #{v['punishment_count'] + 1} recorded.")
    return redirect(url_for('viewer_detail', viewer_id=viewer_id))

@app.post('/viewer/<int:viewer_id>/delete')
def delete_viewer(viewer_id):
    conn = db()
    v = conn.execute('SELECT username FROM viewers WHERE id=?', (viewer_id,)).fetchone()
    if v:
        audit(conn, 'viewer_deleted', viewer_id, details=v['username'])
        conn.execute('DELETE FROM viewers WHERE id=?', (viewer_id,))
        conn.commit()
    conn.close()
    flash('Viewer deleted.')
    return redirect(url_for('viewers'))

@app.route('/streams')
def streams():
    conn = db()
    rows = conn.execute("\n        SELECT s.*,\n               SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS present_count,\n               SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent_count\n        FROM streams s\n        LEFT JOIN attendance a ON a.stream_id=s.id\n        GROUP BY s.id\n        ORDER BY s.id DESC\n    ").fetchall()
    conn.close()
    return render_template('streams.html', streams=rows)

@app.route('/stream/<int:stream_id>')
def stream_detail(stream_id):
    conn = db()
    stream = conn.execute('SELECT * FROM streams WHERE id=?', (stream_id,)).fetchone()
    if not stream:
        conn.close()
        return ('Stream not found', 404)
    rows = conn.execute("\n        SELECT v.id AS viewer_id, v.username, v.display_name, v.tracked,\n               a.status, a.source, a.updated_at\n        FROM viewers v\n        LEFT JOIN attendance a\n          ON a.viewer_id=v.id AND a.stream_id=?\n        WHERE v.tracked=1 OR a.id IS NOT NULL\n        ORDER BY COALESCE(a.status, 'zzz'), v.username COLLATE NOCASE\n    ", (stream_id,)).fetchall()
    conn.close()
    return render_template('stream.html', stream=stream, rows=rows)

@app.post('/streams/start')
def start_stream():
    name = request.form.get('name', '').strip()
    conn = db()
    existing = get_open_stream(conn)
    if existing:
        conn.close()
        flash('A stream is already open.')
        return redirect(url_for('dashboard'))
    if not name:
        name = 'Stream ' + datetime.now().strftime('%Y-%m-%d %H:%M')
    cur = conn.execute('INSERT INTO streams(name, started_at, is_open) VALUES (?,?,1)', (name, now()))
    audit(conn, 'stream_started', stream_id=cur.lastrowid, details=name)
    conn.commit()
    conn.close()
    flash('Attendance session started.')
    return redirect(url_for('dashboard'))

@app.post('/stream/<int:stream_id>/close')
def close_stream(stream_id):
    conn = db()
    result = close_stream_records(conn, stream_id, source='manual-close')
    if not result:
        conn.close()
        return ('Stream not found', 404)
    conn.commit()
    conn.close()
    if result['already_closed']:
        flash('Stream was already closed.')
    else:
        flash(f"Stream closed. {result['new_absences']} missing tracked viewers were marked absent.")
    return redirect(url_for('stream_detail', stream_id=stream_id))

@app.post('/stream/<int:stream_id>/viewer/<int:viewer_id>/status')
def set_stream_status(stream_id, viewer_id):
    status = request.form.get('status')
    if status not in ('present', 'absent'):
        return ('Invalid status', 400)
    conn = db()
    conn.execute("\n        INSERT INTO attendance(stream_id, viewer_id, status, source, updated_at)\n        VALUES (?,?,?,?,?)\n        ON CONFLICT(stream_id, viewer_id)\n        DO UPDATE SET status=excluded.status, source='manual', updated_at=excluded.updated_at\n    ", (stream_id, viewer_id, status, 'manual', now()))
    audit(conn, 'attendance_changed', viewer_id, stream_id, f'status={status}')
    conn.commit()
    conn.close()
    return redirect(url_for('stream_detail', stream_id=stream_id))

@app.post('/stream/<int:stream_id>/delete')
def delete_stream(stream_id):
    conn = db()
    s = conn.execute('SELECT name FROM streams WHERE id=?', (stream_id,)).fetchone()
    if s:
        audit(conn, 'stream_deleted', stream_id=stream_id, details=s['name'])
        conn.execute('DELETE FROM streams WHERE id=?', (stream_id,))
        conn.commit()
    conn.close()
    flash('Stream deleted.')
    return redirect(url_for('streams'))

@app.route('/audit')
def audit_page():
    conn = db()
    rows = conn.execute('\n        SELECT l.*, v.username, s.name AS stream_name\n        FROM audit_log l\n        LEFT JOIN viewers v ON v.id=l.viewer_id\n        LEFT JOIN streams s ON s.id=l.stream_id\n        ORDER BY l.id DESC\n        LIMIT 300\n    ').fetchall()
    conn.close()
    return render_template('audit.html', logs=rows)

@app.route('/api/stream/start', methods=['GET', 'POST'])
def api_stream_start():
    data = request.get_json(silent=True) or request.form or request.args
    requested_name = str(data.get('name', '')).strip()
    conn = db()
    existing = get_open_stream(conn)
    if existing:
        conn.close()
        return jsonify({'ok': True, 'started': False, 'reopened': False, 'already_open': True, 'stream_id': existing['id'], 'name': existing['name']})
    last_closed = conn.execute('\n        SELECT *\n        FROM streams\n        WHERE is_open=0 AND ended_at IS NOT NULL\n        ORDER BY id DESC\n        LIMIT 1\n    ').fetchone()
    if last_closed:
        try:
            ended = datetime.strptime(last_closed['ended_at'], '%Y-%m-%d %H:%M:%S')
            elapsed = datetime.now() - ended
        except (TypeError, ValueError):
            elapsed = timedelta(days=999)
        if timedelta(0) <= elapsed < timedelta(hours=24):
            conn.execute('\n                UPDATE streams\n                SET is_open=1, ended_at=NULL\n                WHERE id=?\n            ', (last_closed['id'],))
            audit(conn, 'stream_reopened_auto', stream_id=last_closed['id'], details=f'reopened_after_seconds={int(elapsed.total_seconds())}')
            conn.commit()
            conn.close()
            return jsonify({'ok': True, 'started': True, 'reopened': True, 'already_open': False, 'stream_id': last_closed['id'], 'name': last_closed['name'], 'reopened_after_seconds': int(elapsed.total_seconds())})
    name = requested_name or 'Attendance Session — ' + datetime.now().strftime('%Y-%m-%d %H:%M')
    cur = conn.execute('INSERT INTO streams(name, started_at, is_open) VALUES (?,?,1)', (name, now()))
    stream_id = cur.lastrowid
    audit(conn, 'stream_started_auto', stream_id=stream_id, details=name)
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'started': True, 'reopened': False, 'already_open': False, 'stream_id': stream_id, 'name': name})

@app.route('/api/stream/stop', methods=['GET', 'POST'])
def api_stream_stop():
    conn = db()
    stream = get_open_stream(conn)
    if not stream:
        conn.close()
        return jsonify({'ok': True, 'stopped': False, 'already_closed': True, 'message': 'no open attendance session'})
    result = close_stream_records(conn, stream['id'], source='auto-stream-stop')
    conn.commit()
    due = []
    viewer_ids = [r['id'] for r in conn.execute('SELECT id FROM viewers WHERE tracked=1').fetchall()]
    for viewer_id in viewer_ids:
        state = get_punishment_state(conn, viewer_id)
        if state['eligible']:
            viewer = conn.execute('SELECT username FROM viewers WHERE id=?', (viewer_id,)).fetchone()
            due.append({'username': viewer['username'], 'absences': state['absent'], 'threshold': state['next_threshold']})
    conn.close()
    return jsonify({'ok': True, 'stopped': True, 'already_closed': False, 'stream_id': stream['id'], 'new_absences': result['new_absences'], 'punishments_due': due})

@app.route('/api/check-in', methods=['GET', 'POST'])
def api_check_in():
    data = request.get_json(silent=True) or request.form or request.args
    username = str(data.get('username', '')).strip().lstrip('@')
    twitch_id = str(data.get('twitch_id', '')).strip() or None
    display_name = str(data.get('display_name', '')).strip() or username
    if not username:
        return (jsonify({'ok': False, 'error': 'username is required'}), 400)
    conn = db()
    stream = get_open_stream(conn)
    if not stream:
        conn.close()
        return (jsonify({'ok': False, 'error': 'no open attendance session', 'punishment_due': False}), 409)
    viewer = None
    if twitch_id:
        viewer = conn.execute('SELECT * FROM viewers WHERE twitch_id=?', (twitch_id,)).fetchone()
    if not viewer:
        viewer = conn.execute('SELECT * FROM viewers WHERE username=? COLLATE NOCASE', (username,)).fetchone()
    if not viewer:
        try:
            cur = conn.execute('\n                INSERT INTO viewers(twitch_id, username, display_name, created_at)\n                VALUES (?,?,?,?)\n            ', (twitch_id, username, display_name, now()))
            viewer_id = cur.lastrowid
            audit(conn, 'viewer_auto_added', viewer_id, stream['id'], username)
        except sqlite3.IntegrityError:
            viewer = conn.execute('SELECT * FROM viewers WHERE username=? COLLATE NOCASE', (username,)).fetchone()
            viewer_id = viewer['id']
    else:
        viewer_id = viewer['id']
        conn.execute('\n            UPDATE viewers\n            SET username=?, display_name=?,\n                twitch_id=COALESCE(twitch_id, ?)\n            WHERE id=?\n        ', (username, display_name, twitch_id, viewer_id))
    conn.execute("\n        INSERT INTO attendance(stream_id, viewer_id, status, source, updated_at)\n        VALUES (?,?,'present','chat',?)\n        ON CONFLICT(stream_id, viewer_id)\n        DO UPDATE SET status='present', source='chat', updated_at=excluded.updated_at\n    ", (stream['id'], viewer_id, now()))
    state = get_punishment_state(conn, viewer_id)
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'stream_id': stream['id'], 'viewer_id': viewer_id, 'username': username, 'status': 'present', 'absences': state['absent'], 'punishment_count': state['punishment_count'], 'timeout_warning': state['eligible'], 'timeout_threshold': state['next_threshold'], 'timeout_number': state['punishment_count'] + 1})

@app.route('/api/punishment/record', methods=['GET', 'POST'])
def api_punishment_record():
    data = request.get_json(silent=True) or request.form or request.args
    username = str(data.get('username', '')).strip().lstrip('@')
    twitch_id = str(data.get('twitch_id', '')).strip() or None
    threshold_raw = str(data.get('threshold', '')).strip()
    note = str(data.get('note', '')).strip()
    if not username and (not twitch_id):
        return (jsonify({'ok': False, 'error': 'username or twitch_id is required'}), 400)
    conn = db()
    viewer = None
    if twitch_id:
        viewer = conn.execute('SELECT * FROM viewers WHERE twitch_id=?', (twitch_id,)).fetchone()
    if not viewer and username:
        viewer = conn.execute('SELECT * FROM viewers WHERE username=? COLLATE NOCASE', (username,)).fetchone()
    if not viewer:
        conn.close()
        return (jsonify({'ok': False, 'error': 'viewer not found'}), 404)
    state = get_punishment_state(conn, viewer['id'])
    threshold = state['next_threshold']
    if threshold_raw:
        try:
            threshold = int(threshold_raw)
        except ValueError:
            pass
    duplicate = conn.execute('SELECT id FROM punishments WHERE viewer_id=? AND absence_threshold=?', (viewer['id'], threshold)).fetchone()
    if duplicate:
        conn.close()
        return jsonify({'ok': True, 'recorded': False, 'duplicate': True, 'viewer_id': viewer['id'], 'threshold': threshold})
    conn.execute('\n        INSERT INTO punishments(viewer_id, absence_threshold, punished_at, note)\n        VALUES (?,?,?,?)\n    ', (viewer['id'], threshold, now(), note or 'Automatic Twitch timeout'))
    audit(conn, 'punishment_recorded_auto', viewer['id'], details=f'threshold={threshold}')
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'recorded': True, 'duplicate': False, 'viewer_id': viewer['id'], 'threshold': threshold})

@app.get('/api/viewer/stats')
def api_viewer_stats():
    username = str(request.args.get('username', '')).strip().lstrip('@')
    twitch_id = str(request.args.get('twitch_id', '')).strip() or None
    if not username and (not twitch_id):
        return (jsonify({'ok': False, 'error': 'username or twitch_id is required'}), 400)
    conn = db()
    viewer = None
    if twitch_id:
        viewer = conn.execute('SELECT * FROM viewers WHERE twitch_id=?', (twitch_id,)).fetchone()
    if not viewer and username:
        viewer = conn.execute('SELECT * FROM viewers WHERE username=? COLLATE NOCASE', (username,)).fetchone()
    if not viewer:
        conn.close()
        return (jsonify({'ok': False, 'error': 'viewer not found'}), 404)
    stats = viewer_stats(conn, viewer['id'])
    history = conn.execute('\n        SELECT a.status\n        FROM attendance a\n        JOIN streams s ON s.id=a.stream_id\n        WHERE a.viewer_id=?\n        ORDER BY s.id DESC\n    ', (viewer['id'],)).fetchall()
    current_streak = 0
    for row in history:
        if row['status'] == 'present':
            current_streak += 1
        else:
            break
    longest_streak = 0
    running = 0
    for row in reversed(history):
        if row['status'] == 'present':
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0
    conn.close()
    return jsonify({'ok': True, 'viewer_id': viewer['id'], 'username': viewer['username'], 'display_name': viewer['display_name'] or viewer['username'], 'present': stats['present'], 'absent': stats['absent'], 'total': stats['total'], 'attendance_rate': stats['rate'], 'current_streak': current_streak, 'longest_streak': longest_streak})

@app.get('/api/status')
def api_status():
    conn = db()
    stream = get_open_stream(conn)
    conn.close()
    return jsonify({'ok': True, 'open_stream': dict(stream) if stream else None})
if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=6767, debug=False)
