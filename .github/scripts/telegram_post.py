#!/usr/bin/env python3
"""Автопостингъ новых матеріаловъ «ЭХЪ!рф» в Telegram-каналъ.

Берёт файлы, добавленные или изменённые в последнем коммите в content/,
и шлёт по одному посту в канал: заголовок, описание, ссылка на матеріал.
Страницы (_index.md, redaktsiya.md) не публикуются.
"""

import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "https://эхъ.рф").rstrip("/")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@ekhrf")
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DRY_RUN = os.environ.get("DRY_RUN") == "1"


def changed_content_files():
    rng = os.environ.get("GIT_RANGE", "HEAD~1..HEAD")
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=AM", rng, "--", "content/"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return []  # первый коммит или нет исторіи — нечего постить
    files = []
    for line in out.splitlines():
        line = line.strip()
        if not line.endswith(".md"):
            continue
        name = os.path.basename(line)
        if name == "_index.md" or name == "redaktsiya.md":
            continue
        files.append(line)
    return files


def parse_front_matter(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^(\w[\w-]*)\s*:\s*(.*)$", line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip().strip('"')
    return fm


def material_url(path):
    rel = os.path.relpath(path, "content").replace(os.sep, "/")
    rel = re.sub(r"\.md$", "", rel)
    rel = re.sub(r"/_index$", "", rel)
    return f"{BASE_URL}/{rel}/"


def post_to_telegram(title, description, url):
    text = f"<b>{html.escape(title)}</b>"
    if description:
        text += f"\n\n{html.escape(description)}"
    text += f'\n\n<a href="{html.escape(url, quote=True)}">Читать далѣе…</a>'
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=data
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if not resp.get("ok"):
        print(f"ОШИБКА: {resp}", file=sys.stderr)
        sys.exit(1)
    print(f"Опубликовано: {title} -> {url}")


def main():
    files = changed_content_files()
    if not files:
        print("Новых матеріаловъ нѣтъ — постить нечего.")
        return

    materials = []
    for path in files:
        fm = parse_front_matter(path)
        if not fm or not fm.get("title"):
            print(f"Пропуск (нет заголовка): {path}", file=sys.stderr)
            continue
        materials.append((fm.get("date", ""), path, fm))
    materials.sort()  # по датѣ, при равных — по пути

    for _, path, fm in materials:
        url = material_url(path)
        if DRY_RUN:
            print(f"[DRY-RUN] {fm['title']} | {fm.get('description', '')} | {url}")
        else:
            post_to_telegram(fm["title"], fm.get("description", ""), url)


if __name__ == "__main__":
    main()
