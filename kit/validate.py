#!/usr/bin/env python3
"""Проверка data.json перед рендером и сдачей. Ноль ошибок обязателен.

    python3 validate.py data.json [--shots-dir shots/] [--allow-missing-screenshots]

Выводит ошибки (сдавать нельзя) и предупреждения (объяснить в README.md).
"""
import json, re, sys, pathlib

CATALOG = ["А-1","А-2","А-3","А-4","А-5","А-6","А-7","А-8","А-9","А-10а","А-10б","А-10в","А-11","А-12",
           "Б-1","Б-2","Б-3","В-1","В-2","В-3","В-4","В-5","Г-1","Г-2","Г-3","Г-4","Г-5","Д-1","Д-2","Д-3","Е-1"]
SECTIONS = ["common","struct","document","education","eduStandarts","managers","employees","objects",
            "paid_edu","budget","vacant","grants","inter","catering"]
# Класс каждой проверки задан каталогом задания (раздел 7); исполнитель менять его не может.
CATALOG_CLS = {"А-1":"violation","А-2":"violation","А-3":"violation","А-4":"violation","А-5":"violation","А-6":"risk",
               "А-7":"violation","А-8":"violation","А-9":"violation","А-10а":"violation","А-10б":"violation","А-10в":"violation",
               "А-11":"check","А-12":"violation","Б-1":"violation","Б-2":"violation","Б-3":"risk",
               "В-1":"violation","В-2":"violation","В-3":"risk","В-4":"risk","В-5":"risk",
               "Г-1":None,"Г-2":"risk","Г-3":"fact","Г-4":"fact","Г-5":"fact","Д-1":"violation","Д-2":"risk","Д-3":"fact","Е-1":"fact"}
W_STATUS = {"violation":1.0,"risk":0.5,"check":0.2,"unverified":0.2,"fact":0.0,"ok":0.0}
W_CLS = {"violation":1.0,"risk":0.5,"check":0.2,"fact":0.0}
W_GROUPS = {"A":0.40,"B":0.15,"V":0.15,"G":0.15,"D":0.15}
GROUP_OF = {"А":"A","Б":"B","В":"V","Г":"G","Д":"D","Е":"E"}
FIO_RE = re.compile(r"[А-ЯЁ][а-яё-]+ [А-ЯЁ][а-яё-]+ [А-ЯЁ][а-яё-]+|[А-ЯЁ][а-яё-]+ [А-ЯЁ]\.\s?[А-ЯЁ]\.")
STATUSES = {"violation","risk","check","unverified","fact","ok"}
CARD_STATUSES = {"violation","risk","check","fact"}
NORM_RE = re.compile(r"(ФЗ-273|273-ФЗ|ст\. ?29|34-ФЗ|1802|1493|1353|920|№ ?102|577|462|152-ФЗ|63-ФЗ|не норма|без внешней нормы|качество площадки)", re.I)
FORBIDDEN_WHERE = re.compile(r"(вся страница|весь html|весь блок|весь раздел|^—$|^-$)", re.I)
TECH_TERMS = re.compile(r"(itemprop|<td|<th|\bhtml\b|snapshot|href|json|fetch|\bcss\b|\bdom\b|manifest|raw header|headless|axe-core|песочниц|\bппс\b|\bоп\b|опоп|фгис|машиночитаем|ячеек)", re.I)
PD_RE = re.compile(r"(\+7[\s(]*\d{3}[\s)]*\d{3}[\s-]*\d{2}[\s-]*\d{2}|[\w.+-]+@(mail\.ru|gmail\.com|yandex\.ru|ya\.ru|bk\.ru|list\.ru|inbox\.ru|rambler\.ru))", re.I)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def main():
    args = sys.argv[1:]
    if not args: print(__doc__); sys.exit(2)
    data = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))
    shots = pathlib.Path(args[args.index("--shots-dir")+1]) if "--shots-dir" in args else pathlib.Path(args[0]).parent
    allow_noshot = "--allow-missing-screenshots" in args
    errors, warns = [], []
    E = errors.append; W = warns.append

    meta = data.get("meta", {})
    for k in ("org","site","snapshot_date","build_date","build","rules"):
        if not meta.get(k): E(f"meta.{k} пусто")
    if meta.get("snapshot_date") and not DATE_RE.match(meta["snapshot_date"]): E("meta.snapshot_date не в формате ГГГГ-ММ-ДД")

    codes = [s.get("code") for s in data.get("sections", [])]
    if codes != SECTIONS: E(f"sections: ожидается ровно 14 подразделов в порядке {SECTIONS}, получено {codes}")

    checks = {c.get("id"): c for c in data.get("checks", [])}
    for cid in CATALOG:
        if cid not in checks: E(f"checks: нет проверки {cid}")
    for cid, c in checks.items():
        if c.get("status") not in STATUSES: E(f"checks {cid}: статус «{c.get('status')}» вне списка")
        if c.get("status") == "unverified" and not c.get("note"): E(f"checks {cid}: «не проверено» без причины в note")
        if c.get("status") == "violation" and c.get("cls") != "violation": E(f"checks {cid}: статус «нарушение» при классе «{c.get('cls')}»")
        want = CATALOG_CLS.get(cid)
        if want and c.get("cls") != want: E(f"checks {cid}: класс «{c.get('cls')}», а по каталогу задания «{want}»; класс проверки менять нельзя")
        if PD_RE.search(str(c.get("note",""))): E(f"checks {cid}: в примечании незамаскированный личный телефон или личная почта")
        if TECH_TERMS.search(str(c.get("note",""))): W(f"checks {cid}: в примечании технический термин, перепишите словами")
    snap_missing = [s["code"] for s in data.get("sections", []) if s.get("snapshot_ok") is False]
    if snap_missing and checks.get("А-1", {}).get("status") == "ok": E(f"А-1 «соответствует», но страницы без снимка: {snap_missing}")

    seen_cause = {}
    for f in data.get("findings", []):
        fid = f.get("id","?")
        if f.get("status") not in CARD_STATUSES: E(f"{fid}: статус «{f.get('status')}» недопустим для карточки («не проверено» и «соответствует» карточками не бывают)")
        if f.get("check") not in checks: E(f"{fid}: ссылка на несуществующую проверку {f.get('check')}")
        if f.get("status") == "violation" and checks.get(f.get("check"), {}).get("cls") != "violation": E(f"{fid}: «нарушение» при классе проверки «{checks.get(f.get('check'), {}).get('cls')}»")
        for k in ("title","evidence","source","norm","fix","owner","due","first_seen","section","where"):
            if not f.get(k): E(f"{fid}: поле {k} пусто")
        if f.get("section") not in SECTIONS: E(f"{fid}: подраздел «{f.get('section')}» вне 14")
        for w in f.get("where", []):
            if not str(w.get("url","")).startswith("http"): E(f"{fid}: «Где» без ссылки http: {w}")
            if FORBIDDEN_WHERE.search(str(w.get("hint",""))) or FORBIDDEN_WHERE.search(str(w.get("label",""))): E(f"{fid}: «Где» не указывает место: {w.get('label')} / {w.get('hint')}")
            if f.get("status") in ("violation","risk") and not w.get("hint"): W(f"{fid}: у «Где» нет подсказки «где именно» (строка, файл, якорь)")
        shot = f.get("screenshot","")
        b64 = str(f.get("screenshot_b64","") or "")
        if b64 and not re.match(r"^data:image/(png|jpe?g|webp);base64,[A-Za-z0-9+/=]{100,}$", b64):
            E(f"{fid}: screenshot_b64 не является картинкой png/jpg в base64")
        if not shot or not re.search(r"\.(png|jpe?g|webp)$", str(shot), re.I):
            (W if allow_noshot else E)(f"{fid}: скриншот не приложен файлом (png/jpg): «{shot}»")
        elif not (shots / shot).exists() and not pathlib.Path(shot).exists() and not b64:
            (W if allow_noshot else E)(f"{fid}: файл скриншота не найден: {shot} (приложите файл или вложите картинку в screenshot_b64)")
        if f.get("status") == "violation" and not NORM_RE.search(f.get("norm","")): E(f"{fid}: «нарушение» с нормой вне таблицы раздела 3: «{f.get('norm')}»")
        if TECH_TERMS.search(f.get("title","")): E(f"{fid}: в «Что не так» технический термин: «{f.get('title')}»")
        if len(f.get("title","")) > 160: W(f"{fid}: «Что не так» длиннее 160 знаков")
        if not DATE_RE.match(str(f.get("due",""))): E(f"{fid}: срок не дата ГГГГ-ММ-ДД: «{f.get('due')}»")
        owner = f.get("owner","")
        if "," not in owner and "ФИО на сайте не найдено" not in owner: E(f"{fid}: «Кто» без должности и ФИО через запятую: «{owner}»")
        elif "ФИО на сайте не найдено" not in owner and not FIO_RE.search(owner): E(f"{fid}: в «Кто» нет ФИО; если его нет на сайте, напишите «ФИО на сайте не найдено»: «{owner}»")
        if PD_RE.search(f.get("title","")+" "+f.get("evidence","")+" "+" ".join(r.get("text","") for r in f.get("rows",[]))): E(f"{fid}: в карточке личный телефон или личная почта, замаскируйте")
        for r in f.get("rows", []):
            if r.get("url") is not None and not str(r.get("url","")).startswith("http"): E(f"{fid}: строка списка без ссылки http: {r.get('text')}")
        key = (f.get("section"), f.get("where",[{}])[0].get("url"), f.get("status"))
        seen_cause.setdefault(key, []).append(fid)
        shot_key = ("shot", f.get("screenshot"))
        if re.search(r"\.(png|jpe?g|webp)$", str(f.get("screenshot","")), re.I): seen_cause.setdefault(shot_key, []).append(fid)
    for key, ids in seen_cause.items():
        if len(ids) > 1 and key[0] == "shot": E(f"одна первопричина разбита на несколько карточек (один и тот же скриншот {key[1]}): {ids}; объедините в одну карточку с перечнем проверок")
        elif len(ids) > 1: W(f"возможные дубли одной первопричины (один подраздел, одно место, один статус): {ids}; объедините, если причина одна")

    # Индекс и счётчики пересчитываются из checks/findings; расхождение с data.json — ошибка.
    num, den = {}, {}
    for cid, c in checks.items():
        g = GROUP_OF.get(cid[0]); wc = W_CLS.get(c.get("cls"))
        if g is None or g == "E" or wc is None: continue
        num[g] = num.get(g, 0.0) + min(W_STATUS.get(c.get("status"), 0.0), wc); den[g] = den.get(g, 0.0) + wc
    calc = {g: round(100 * (1 - num[g] / den[g]), 2) for g in den if den[g]}
    # Блок scores необязателен (дашборд считает индекс сам); если он есть, он обязан совпадать с расчётом.
    given = data.get("scores") or {}
    name = {"A":"S_A","B":"S_B","V":"S_V","G":"S_G","D":"S_D"}
    for g, sg in calc.items():
        gv = given.get(name[g])
        if gv is not None and abs(float(gv) - sg) > 0.6: E(f"scores.{name[g]} = {gv}, а по проверкам выходит {sg}; индекс считается из checks, не переносится из прошлой сборки")
    if all(g in calc for g in W_GROUPS):
        I = round(sum(W_GROUPS[g] * calc[g] for g in W_GROUPS), 2)
        if given.get("I") is not None and abs(float(given["I"]) - I) > 0.6: E(f"scores.I = {given.get('I')}, а по формуле выходит {I}")
        for r in data.get("registry", []):
            if "индекс" in str(r.get("method","")).lower() and re.match(r"^\d+([.,]\d+)?$", str(r.get("value",""))) and abs(float(str(r["value"]).replace(",", ".")) - I) > 0.6:
                E(f"registry: индекс {r['value']}, а по формуле выходит {I}")
    fnd = data.get("findings", [])
    cnt = data.get("counters") or {}
    real = {"violations_root": sum(1 for f in fnd if f.get("status") == "violation"),
            "risks": sum(1 for f in fnd if f.get("status") == "risk"),
            "unverified": sum(1 for c in checks.values() if c.get("status") == "unverified"),
            "findings_total": len(fnd)}
    for k, v in real.items():
        if cnt.get(k) is not None and int(cnt[k]) != v: E(f"counters.{k} = {cnt[k]}, а по данным {v}")
    des = (meta.get("design") or {})
    site_host = re.sub(r"^https?://(www\.)?", "", meta.get("site", "")).split("/")[0]
    if not des: W("meta.design пуст: токены оформления берутся с проверяемого сайта (раздел 10.1)")
    else:
        if site_host and site_host not in str(des.get("source", "")): E(f"meta.design.source не ссылается на стили {site_host}: «{des.get('source')}»")
        if not des.get("logo"): W("meta.design.logo пуст: логотип вуза с главной страницы не сохранён")

    reg = data.get("registry", [])
    if not reg: E("registry пуст")
    for r in reg:
        if not all(r.get(k) for k in ("value","source","date","method")): E(f"registry: неполная строка {r}")

    print(f"ОШИБОК: {len(errors)}   ПРЕДУПРЕЖДЕНИЙ: {len(warns)}")
    try:
        for e in errors: print("ОШИБКА  ", e)
        for w in warns: print("ПРЕДУПР ", w)
    except BrokenPipeError:
        pass
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
