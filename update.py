#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会议截稿数据更新脚本。
用法:  python3 update.py
会联网抓取软工四大顶会的最新重要日期，更新同目录下 index.html 里内联的数据块。
历史投稿/录用统计不自动抓取（需人工维护），脚本保留原值。

依赖: 仅 Python 标准库（urllib + re + json）。
"""
import json
import re
import sys
import urllib.request
from datetime import date

HERE = __file__.rsplit("/", 1)[0] + "/"
INDEX_HTML = HERE + "index.html"

USER_AGENT = "Mozilla/5.0 (compatible; conf-tracker/1.0)"
TIMEOUT = 20


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_researchr_dates(html):
    """从 conf.researchr.org/dates/<conf> 解析 {track: {what: 'YYYY-MM-DD'}}"""
    out = {}
    rows = re.findall(
        r"<tr[^>]*>\s*<td[^>]*>([^<]+?)</td>\s*<td[^>]*>([^<]*?)</td>\s*<td[^>]*>([^<]*?)</td>",
        html, re.I | re.S,
    )
    months = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
    }
    for when, track, what in rows:
        m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", when)
        if not m:
            continue
        d, mon, y = int(m.group(1)), months.get(m.group(2)[:3].title()), int(m.group(3))
        if not mon:
            continue
        iso = "%04d-%02d-%02d" % (y, mon, d)
        key = re.sub(r"\s+", " ", what.strip())
        track = re.sub(r"\s+", " ", track.strip())
        out.setdefault(track, {})[key] = iso
    return out


def find_conf(data, key):
    for g in data["groups"]:
        for c in g["conferences"]:
            if c["key"] == key:
                return c
    raise KeyError(key)


def update_from_researchr(conf_key, url, data):
    try:
        html = fetch(url)
    except Exception as e:
        print("  [warn] 抓取失败 %s: %s" % (url, e))
        return
    parsed = parse_researchr_dates(html)
    if not parsed:
        print("  [warn] 未解析到日期 %s" % url)
        return
    conf = find_conf(data, conf_key)
    ed = conf["editions"][0]
    today = date.today().isoformat()
    for track, items in parsed.items():
        sub = items.get("Full paper submission") or items.get("Submission") or items.get("Paper Submission")
        abst = items.get("Mandatory Abstract submission") or items.get("Abstract submission")
        notif = items.get("Initial Notification") or items.get("Author notification") or items.get("Final Notification")
        cyc = next((c for c in ed["cycles"]
                   if c["track"].lower() in track.lower() or track.lower() in c["track"].lower()), None)
        if not cyc:
            cyc = {"track": track, "tz": "AoE"}
            ed["cycles"].append(cyc)
        if abst:
            cyc["abstract"] = abst
        if sub:
            cyc["submission"] = sub
            cyc["status"] = "open" if sub >= today else "closed"
        if notif:
            cyc["notification"] = notif
    print("  [ok] %s 已更新" % conf_key)


def load_current():
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    m = re.search(r"<script id=\"data\">\s*window\.CONF_DATA\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        raise RuntimeError("无法从 index.html 解析内联数据块")
    return json.loads(m.group(1)), html


def save_data(data, html):
    body = "window.CONF_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";"
    new_html = re.sub(
        r"<script id=\"data\">\s*window\.CONF_DATA\s*=\s*\{.*?\};\s*</script>",
        "<script id=\"data\">\n" + body + "\n</script>",
        html, count=1, flags=re.S,
    )
    if new_html == html:
        raise RuntimeError("替换失败，未匹配到数据块")
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)


SOURCES = [
    ("icse", "https://conf.researchr.org/dates/icse-2027"),
    ("fse", "https://conf.researchr.org/dates/fse-2027"),
    ("ase", "https://conf.researchr.org/dates/ase-2026"),
    ("issta", "https://conf.researchr.org/dates/issta-2027"),
]


def main():
    print("== 会议截稿数据更新 ==")
    data, html = load_current()
    for key, url in SOURCES:
        print("更新 %s <- %s" % (key, url))
        update_from_researchr(key, url, data)
    data["last_updated"] = date.today().isoformat()
    save_data(data, html)
    print("\n完成。index.html 已更新，last_updated =", data["last_updated"])
    print("提示: 安全四大 (S&P/CCS/USENIX/NDSS) 官网结构各异，本脚本暂未自动解析，")
    print("      如需更新请手动改 index.html 里的内联数据块，或扩展本脚本解析逻辑。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("已中断")
