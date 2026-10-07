#!/usr/bin/env python3
"""Построчная проверка ссылок раздела «Сведения об образовательной организации».

Запускать с российского адреса (сайт закрыт защитой для зарубежных IP):
    python3 check_links.py https://pnzgu.ru > links.csv

Что делает: обходит 14 страниц /sveden/*, собирает все ссылки, каждую пробует
запросом GET и решает по телу ответа, а не по коду: сервер отдаёт 200 почти на всё.
Вердикты: живая · мёртвая (ошибка соединения или код 4xx/5xx) · заглушка (страница
«Ошибка 404» с кодом 200) · не файл (ожидался документ, пришла HTML-страница).
Результат: CSV со столбцами страница; текст ссылки; адрес; код; тип; размер; вердикт.
Только стандартная библиотека, 2 запроса в секунду.
"""
import sys, csv, time, re, urllib.request, urllib.error, urllib.parse
from html.parser import HTMLParser

SECTIONS = ["common","struct","document","education","eduStandarts","managers","employees",
            "objects","paid_edu","budget","vacant","grants","inter","catering"]
UA = {"User-Agent": "site-vuz audit link checker (контакт: ЦНИТ вуза)"}
DOC_EXT = re.compile(r"\.(pdf|docx?|xlsx?|odt|ods|rtf|zip|sig)(\?|$)", re.I)

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag=="a":
            self._href=dict(attrs).get("href"); self._text=[]
    def handle_data(self, d):
        if self._href is not None: self._text.append(d)
    def handle_endtag(self, tag):
        if tag=="a" and self._href:
            self.links.append((self._href, " ".join("".join(self._text).split())[:120])); self._href=None

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(400000)
            return r.status, r.headers.get("Content-Type",""), r.headers.get("Last-Modified",""), len(body), body
    except urllib.error.HTTPError as e:
        return e.code, "", "", 0, b""
    except Exception as e:
        return 0, str(e)[:60], "", 0, b""

def verdict(url, code, ctype, lastmod, size, body):
    if code == 0 or code >= 400: return "мёртвая"
    text = body[:4000].decode("utf-8", "ignore").lower()
    if "ошибка 404" in text or "страница не найдена" in text or (size and size < 600 and "html" in ctype): return "заглушка"
    if DOC_EXT.search(url) and "html" in ctype: return "не файл"
    return "живая"

def main():
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://pnzgu.ru"
    w = csv.writer(sys.stdout, delimiter=";")
    w.writerow(["страница","текст ссылки","адрес","код","тип","размер","last-modified","вердикт"])
    seen = {}
    for sec in SECTIONS:
        page = f"{base}/sveden/{sec}"
        code, ctype, lm, size, body = fetch(page)
        if code != 200:
            w.writerow([page,"(страница)",page,code,ctype,size,lm,"мёртвая"]); continue
        p = Links(); p.feed(body.decode("utf-8","ignore"))
        for href, text in p.links:
            if href.startswith(("mailto:","tel:","javascript:","#")): continue
            url = urllib.parse.urljoin(page, href)
            if url not in seen:
                time.sleep(0.5)
                c, ct, l, sz, b = fetch(url)
                seen[url] = (c, ct, l, sz, verdict(url, c, ct, l, sz, b))
            c, ct, l, sz, v = seen[url]
            w.writerow([page, text, url, c, ct.split(";")[0], sz, l, v])
            sys.stdout.flush()

if __name__ == "__main__":
    main()
