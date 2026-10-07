#!/usr/bin/env python3
"""Рендер дашборда аудита из data.json. Исполнитель не меняет этот файл и template.html.

    python3 render.py data.json out/            # -> out/index.html (пререндер, работает без JavaScript)

Токены оформления берутся из data.json: meta.design (brand_primary, brand_secondary, background,
font_heading, font_body, logo, radius). Цвета статусов фиксированы и из данных не берутся.
"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).parent

def design_css(d):
    if not d: return ""
    rules = []
    if d.get("brand_primary"): rules.append(f"--accent:{d['brand_primary']}")
    if d.get("radius"): rules.append(f"--radius:{d['radius']}")
    if d.get("font_heading"): rules.append(f"--display:\"{d['font_heading']}\",\"Manrope\",system-ui,sans-serif")
    if d.get("font_body"): rules.append(f"--body:\"{d['font_body']}\",\"IBM Plex Sans\",system-ui,sans-serif")
    if d.get("background"): rules.append(f"--bg:{d['background']}")
    css = ":root{" + ";".join(rules) + "}" if rules else ""
    if d.get("radius"):
        css += " .kpi,.verdict,.panel,.card,.tbl,.placeholder,details.meth{border-radius:var(--radius)}"
    if d.get("font_link"):
        css = f'<link rel="stylesheet" href="{d["font_link"]}">' + "<style>" + css + "</style>"
    else:
        css = "<style>" + css + "</style>"
    return css

def render(data_path, out_dir, prerender=True):
    data = json.loads(pathlib.Path(data_path).read_text(encoding="utf-8"))
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    body = tpl.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    body = body.replace("<!--__DESIGN__-->", design_css(data.get("meta", {}).get("design")))
    html = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="color-scheme" content="light dark">\n'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)} body{margin:0} img{max-width:100%} [hidden]{display:none!important}</style>\n'
            '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    target = out / "index.html"
    target.write_text(html, encoding="utf-8")
    if prerender:
        try:
            target.write_text(_prerender(target), encoding="utf-8"); print("пререндер выполнен")
        except Exception as e:
            print("пререндер пропущен (нужен playwright + chromium):", e)
    print("готово:", target)

def _prerender(path):
    import asyncio
    from playwright.async_api import async_playwright
    async def run():
        async with async_playwright() as p:
            exe = pathlib.Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
            br = await (p.chromium.launch(executable_path=str(exe)) if exe.exists() else p.chromium.launch())
            pg = await br.new_page(viewport={"width": 1100, "height": 900})
            await pg.goto(path.resolve().as_uri(), wait_until="load"); await pg.wait_for_timeout(500)
            await pg.click("#filters button[data-all]")
            await pg.evaluate("""() => { document.querySelectorAll('textarea').forEach(t => { t.textContent = t.value; });
                                      document.querySelectorAll('details.meth').forEach(d => d.open = true);
                                      document.body.setAttribute('data-prerendered','1'); }""")
            html = await pg.evaluate("'<!doctype html>\\n' + document.documentElement.outerHTML")
            await br.close(); return html
    return asyncio.run(run())

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    render(sys.argv[1], sys.argv[2], prerender="--no-prerender" not in sys.argv)
