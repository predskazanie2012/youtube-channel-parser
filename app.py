#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import queue
import re
import socket
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
import yt_dlp

BASE_DIR = Path(__file__).parent
app = Flask(__name__, template_folder=str(BASE_DIR / 'templates'))

from local_access import protect_flask
protect_flask(app)

app.config['JSON_AS_ASCII'] = False

_progress_queue: queue.Queue = queue.Queue()
_is_parsing = False
_parse_lock = threading.Lock()


def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
            return False
        return bool(re.match(r'^/(?:@[^/]+|(?:channel|c|user)/[^/]+)(?:/|$)', parsed.path))
    except Exception:
        return False


def clean_name(name: str) -> str:
    for c in '<>:"/\\|?*':
        name = name.replace(c, '_')
    return name.strip() or 'unknown'


def run_parse(channel_url: str, pq: queue.Queue) -> None:
    global _is_parsing
    try:
        pq.put({'type': 'step', 'step': 1})

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
            'skip_download': True,
            'no_color': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

        if not info:
            pq.put({'type': 'error', 'message': 'Не удалось получить информацию о канале'})
            return

        pq.put({'type': 'step_done', 'step': 1})
        pq.put({'type': 'step', 'step': 2})

        entries = info.get('entries') or []
        video_links = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get('_type') == 'playlist':
                for pe in entry.get('entries') or []:
                    if not isinstance(pe, dict):
                        continue
                    vid = pe.get('id')
                    if isinstance(vid, str) and re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
                        video_links.append(f'https://www.youtube.com/watch?v={vid}')
            else:
                vid = entry.get('id')
                if isinstance(vid, str) and re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
                    video_links.append(f'https://www.youtube.com/watch?v={vid}')

        pq.put({'type': 'step_done', 'step': 2})

        if not video_links:
            pq.put({'type': 'done', 'count': 0, 'file': None, 'channel': '', 'links': []})
            return

        pq.put({'type': 'step', 'step': 3})

        channel_name = clean_name(
            info.get('uploader') or info.get('channel') or
            info.get('uploader_id') or info.get('channel_id') or 'unknown'
        )

        output_dir = BASE_DIR / 'output'
        output_dir.mkdir(exist_ok=True)
        filename = f'{channel_name}_videos.txt'
        output_file = output_dir / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            for link in video_links:
                f.write(f'{link}\n')
            f.write('\n---\n')
            f.write(f'Всего видео найдено: {len(video_links)}\n')
            f.write(f'Дата парсинга: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            f.write(f'Канал: {channel_name}\n')

        pq.put({'type': 'step_done', 'step': 3})
        pq.put({
            'type': 'done',
            'count': len(video_links),
            'file': filename,
            'channel': channel_name,
            'links': video_links[:200],
        })

    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        if 'not found' in err.lower() or 'unavailable' in err.lower():
            msg = 'Канал не найден. Проверьте URL.'
        else:
            msg = f'Ошибка доступа к каналу: {err[:300]}'
        pq.put({'type': 'error', 'message': msg})
    except Exception as e:
        pq.put({'type': 'error', 'message': f'Ошибка: {str(e)[:300]}'})
    finally:
        _is_parsing = False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/parse', methods=['POST'])
def parse():
    global _is_parsing, _progress_queue
    with _parse_lock:
        if _is_parsing:
            return jsonify({'error': 'Парсинг уже выполняется, подождите'}), 429

        data = request.get_json() or {}
        url = data.get('url', '').strip()

        if not validate_url(url):
            return jsonify({'error': 'Некорректный URL. Пример: https://www.youtube.com/@channelname'}), 400

        _is_parsing = True
        _progress_queue = queue.Queue()

    threading.Thread(target=run_parse, args=(url, _progress_queue), daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/stream')
def stream():
    pq = _progress_queue

    def generate():
        while True:
            try:
                msg = pq.get(timeout=60)
                yield f'data: {json.dumps(msg, ensure_ascii=False)}\n\n'
                if msg.get('type') in ('done', 'error'):
                    break
            except queue.Empty:
                yield f'data: {json.dumps({"type": "ping"})}\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/download/<path:filename>')
def download(filename):
    return send_from_directory(str(BASE_DIR / 'output'), filename, as_attachment=True)


def find_free_port(start: int = 5000) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    return start


if __name__ == '__main__':
    port = find_free_port()
    url = f'http://localhost:{port}'
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f'\n  YouTube Parser: {url}')
    print('  Браузер откроется автоматически...')
    print('  Закройте это окно для остановки\n')
    app.run(debug=False, port=port, threaded=True)
