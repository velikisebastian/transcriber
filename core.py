"""Общая логика: загрузка в AssemblyAI, ожидание, сборка Markdown."""
import re
import time
from datetime import datetime
from pathlib import Path

import requests

API = "https://api.assemblyai.com/v2"
KEY_URL = "https://www.assemblyai.com/dashboard/api-keys"
MEDIA_EXT = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma", ".amr",
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv", ".3gp",
}
LANGS = [
    ("Определить автоматически", None), ("Русский", "ru"), ("English", "en"),
    ("Українська", "uk"), ("Deutsch", "de"), ("Español", "es"),
    ("Français", "fr"), ("Italiano", "it"), ("Português", "pt"),
    ("Türkçe", "tr"), ("中文", "zh"), ("日本語", "ja"),
]


def fmt_ts(ms):
    s = int(ms // 1000)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def safe_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "transcript"


class Cancelled(Exception):
    pass


def _check(r):
    if r.status_code == 401:
        raise RuntimeError("Неверный API-ключ. Проверьте его в настройках.")
    if not r.ok:
        try:
            msg = r.json().get("error", r.text)
        except Exception:
            msg = r.text
        raise RuntimeError(f"AssemblyAI {r.status_code}: {msg}")
    return r


def transcribe(path, out_dir, key, lang, speakers, stamps, progress, cancelled):
    """Возвращает путь к .md. progress(text, pct); cancelled() -> bool."""
    path, out_dir = Path(path), Path(out_dir)
    h = {"authorization": key}

    def chunks():
        total = path.stat().st_size or 1
        sent = 0
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                if cancelled():
                    raise Cancelled("Отменено")
                sent += len(chunk)
                progress("Загрузка файла…", int(sent / total * 50))
                yield chunk

    progress("Загрузка файла…", 0)
    r = _check(requests.post(f"{API}/upload", headers=h, data=chunks(), timeout=3600))
    body = {"audio_url": r.json()["upload_url"], "punctuate": True,
            "format_text": True, "speaker_labels": speakers}
    if lang:
        body["language_code"] = lang
    else:
        body["language_detection"] = True
    tid = _check(requests.post(f"{API}/transcript", headers=h, json=body, timeout=60)).json()["id"]

    progress("Распознавание…", 60)
    tick = 0
    while True:
        if cancelled():
            raise Cancelled("Отменено")
        data = _check(requests.get(f"{API}/transcript/{tid}", headers=h, timeout=60)).json()
        if data["status"] == "completed":
            break
        if data["status"] == "error":
            raise RuntimeError(data.get("error", "Ошибка распознавания"))
        tick += 1
        progress("Распознавание…", min(95, 60 + tick * 2))
        time.sleep(3)

    progress("Сохранение…", 98)
    paragraphs = []
    if not speakers:
        paragraphs = _check(requests.get(f"{API}/transcript/{tid}/paragraphs",
                                         headers=h, timeout=60)).json().get("paragraphs", [])
    md = markdown(path, data, paragraphs, speakers, stamps)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{safe_name(path.stem)}.md"
    n = 1
    while out.exists():
        n += 1
        out = out_dir / f"{safe_name(path.stem)} ({n}).md"
    out.write_text(md, encoding="utf-8")
    return str(out)


def markdown(path, data, paragraphs, speakers, stamps):
    lines = [f"# {path.stem}", "", f"- **Файл:** {path.name}"]
    if data.get("audio_duration"):
        lines.append(f"- **Длительность:** {fmt_ts(data['audio_duration'] * 1000)}")
    if data.get("language_code"):
        lines.append(f"- **Язык:** {data['language_code']}")
    lines += [f"- **Дата:** {datetime.now():%Y-%m-%d %H:%M}", "", "---", ""]
    ts = (lambda ms: f"`[{fmt_ts(ms)}]` ") if stamps else (lambda ms: "")
    if speakers and data.get("utterances"):
        for u in data["utterances"]:
            lines += [f"{ts(u['start'])}**Спикер {u['speaker']}:** {u['text']}", ""]
    elif paragraphs:
        for p in paragraphs:
            lines += [f"{ts(p['start'])}{p['text']}", ""]
    else:
        lines += [data.get("text") or "_(речь не найдена)_", ""]
    return "\n".join(lines)
