#!/usr/bin/env python3
"""
NexLoop / Tapmore carousel renderer.

Usage:
    bash scripts/setup.sh                      # once per session
    python3 scripts/render.py post.json --out out/

Writes out/slide_01.jpg ... (1080x1350 JPEG, sRGB, < 8 MB, what the Instagram API accepts),
out/contact.png (all slides side by side), out/manifest.json (files, alt text, warnings).

SPEC
{
  "theme": "tapmore" | "nexloop",
  "handle": "@nexloop.io",                 # optional, shown small on the cover and CTA
  "slides": [ {slide}, ... ]               # 6-10 slides; Instagram max is 20
}

Every slide: "type", optional "bg" (light | alt | dark | accent), "kicker" (small label),
"alt" (alt text, required). Text markup: *word* = accent (1-3 words per slide),
~~word~~ = strike-through, \n = line break you choose.

Slide types and fields:
  cover   title, kicker, sub            Big hook. 8 words max in title. Swipe cue added.
  text    title, body                   One idea + up to 30 words.
  stat    number, title, body, source   One big number. Needs a real source or "illustrative".
  list    title, items[{t, s}]          Up to 5 items (t = line, s = optional small line).
  steps   title, steps[{t, s}]          Up to 4 numbered steps.
  grid    title, cards[{icon, t, s}]    Exactly 4 cards. Icons: menu stamp chat star wifi qr
                                        bolt bot clock chart phone calendar repeat whatsapp
                                        globe code users ticket
  phone   title, body, screen{name, tagline, rows[...]}   Illustrative phone page (tapmore look).
                                        rows: {"kind":"stamps","on":6,"of":8,"label":"..."} |
                                              {"kind":"wifi","ssid":"..."} |
                                              {"kind":"menu","items":[["Cold brew","₹180"],...]} |
                                              {"kind":"rating","label":"How was your visit?"} |
                                              {"kind":"chat","msgs":[["in","text"],["out","text"]]}
  compare title, left{label, items[]}, right{label, items[]}   Before/after or old/new.
  cta     title, sub, chips[], qr (url), link (text shown next to the QR)
"""
import sys, json, os, re, html, asyncio, glob, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "fonts")

# ---------------------------------------------------------------- themes
THEMES = {
    "tapmore": {
        "light": ("#F3ECE1", "#1E1916", "#7A6D63", "#C4572F", "#E2D8CA", "#FBF7F0"),
        "alt":   ("#FBF7F0", "#1E1916", "#7A6D63", "#C4572F", "#E2D8CA", "#F3ECE1"),
        "dark":  ("#1E1916", "#F3ECE1", "#B8AA9C", "#E8C9B6", "#3A322D", "#2A2420"),
        "accent":("#C4572F", "#FBF7F0", "#F6DDCF", "#FBF7F0", "#D9775A", "#B54E29"),
        "head_font": "Fraunces", "head_weight": 400, "head_case": "none", "head_track": "-0.03em",
        "accent_font": "Instrument", "accent_style": "italic", "lh": 1.02,
        "wordmark": 'tap<i>more</i>', "grain": True,
    },
    "nexloop": {
        "light": ("#F8F8F6", "#0D0D0D", "#6B6B66", "#2F4BFF", "#E3E3DE", "#FFFFFF"),
        "alt":   ("#FFFFFF", "#0D0D0D", "#6B6B66", "#2F4BFF", "#E8E8E3", "#F3F3EF"),
        "dark":  ("#0D0D0D", "#F8F8F6", "#9A9A94", "#7D93FF", "#2A2A28", "#1A1A19"),
        "accent":("#2F4BFF", "#FFFFFF", "#D6DDFF", "#0D0D0D", "#5A71FF", "#2840E0"),
        "head_font": "Inter", "head_weight": 900, "head_case": "uppercase", "head_track": "-0.045em",
        "accent_font": "Inter", "accent_style": "normal", "lh": 0.92,
        "wordmark": 'NEXLOOP<i>.</i>', "grain": False,
    },
}

ICONS = {
    "menu": '<rect x="10" y="6" width="28" height="36" rx="4"/><path d="M17 16h14M17 24h14M17 32h8"/>',
    "stamp": '<circle cx="14" cy="18" r="5"/><circle cx="34" cy="18" r="5"/><circle cx="14" cy="34" r="5"/><circle cx="34" cy="34" r="5" stroke-dasharray="3 3"/>',
    "chat": '<path d="M8 12h32v20H22l-8 7v-7H8z"/><path d="M17 22h14"/>',
    "star": '<path d="M24 7l5 11 12 1-9 8 3 12-11-6-11 6 3-12-9-8 12-1z"/>',
    "wifi": '<path d="M7 19a25 25 0 0 1 34 0M13 26a16 16 0 0 1 22 0M19 33a7 7 0 0 1 10 0"/><circle cx="24" cy="39" r="1.5"/>',
    "qr": '<rect x="8" y="8" width="13" height="13"/><rect x="27" y="8" width="13" height="13"/><rect x="8" y="27" width="13" height="13"/><path d="M27 27h5v5h-5zM35 35h5v5h-5zM27 37h3M37 27v3"/>',
    "bolt": '<path d="M27 5L11 27h12l-3 16 17-23H25z"/>',
    "bot": '<rect x="9" y="15" width="30" height="22" rx="6"/><path d="M24 15V8"/><circle cx="24" cy="7" r="2"/><circle cx="18" cy="26" r="2"/><circle cx="30" cy="26" r="2"/>',
    "clock": '<circle cx="24" cy="24" r="16"/><path d="M24 14v10l7 5"/>',
    "chart": '<path d="M8 40h32"/><path d="M13 34V24M21 34V16M29 34V20M37 34V10"/>',
    "phone": '<rect x="14" y="5" width="20" height="38" rx="4"/><path d="M21 37h6"/>',
    "calendar": '<rect x="8" y="10" width="32" height="30" rx="4"/><path d="M8 19h32M16 6v8M32 6v8"/>',
    "repeat": '<path d="M10 20a14 14 0 0 1 25-7l3 3M38 28a14 14 0 0 1-25 7l-3-3"/><path d="M38 9v7h-7M10 39v-7h7"/>',
    "whatsapp": '<path d="M24 7a17 17 0 0 0-15 25L7 41l9-2a17 17 0 1 0 8-32z"/><path d="M18 17c0 7 6 13 13 13l2-3-4-2-2 2c-2-1-4-3-5-5l2-2-2-4z"/>',
    "globe": '<circle cx="24" cy="24" r="16"/><path d="M8 24h32M24 8c5 5 5 27 0 32M24 8c-5 5-5 27 0 32"/>',
    "code": '<path d="M17 14L7 24l10 10M31 14l10 10-10 10M27 10l-6 28"/>',
    "users": '<circle cx="18" cy="17" r="6"/><path d="M6 39c0-7 5-12 12-12s12 5 12 12"/><circle cx="33" cy="19" r="5"/><path d="M33 28c5 0 9 4 9 10"/>',
    "ticket": '<path d="M7 15h34v6a3 3 0 0 0 0 6v6H7v-6a3 3 0 0 0 0-6z"/><path d="M28 15v18" stroke-dasharray="3 3"/>',
}

def md(s):
    s = html.escape(s or "")
    s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s.replace("\\n", "<br>").replace("\n", "<br>")

def words(s):
    return len(re.sub(r"[*~\\n]", " ", s or "").split())

def qr_svg(url, color):
    import qrcode, qrcode.image.svg
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=0)
    s = img.to_string(encoding="unicode")
    s = s[s.index("<svg"):]
    s = re.sub(r'width="[^"]*" height="[^"]*"', "", s, count=1)
    return s.replace("<path ", f'<path fill="{color}" ', 1)

# ---------------------------------------------------------------- css
def font_faces():
    f = lambda p: "file://" + os.path.join(FONTS, p)
    out = []
    for w in (400, 600):
        out.append(f"@font-face{{font-family:Fraunces;font-weight:{w};src:url({f(f'fraunces/files/fraunces-latin-{w}-normal.woff2')})}}")
    out.append(f"@font-face{{font-family:Instrument;font-style:italic;src:url({f('instrument-serif/files/instrument-serif-latin-400-italic.woff2')})}}")
    for w in (400, 500, 600, 700, 800, 900):
        out.append(f"@font-face{{font-family:Inter;font-weight:{w};src:url({f(f'inter/files/inter-latin-{w}-normal.woff2')})}}")
    return "\n".join(out)

def css(t):
    th = THEMES[t]
    bgs = ""
    for k in ("light", "alt", "dark", "accent"):
        bg, ink, muted, acc, line, card = th[k]
        bgs += f".bg-{k}{{--bg:{bg};--ink:{ink};--muted:{muted};--acc:{acc};--line:{line};--card:{card}}}\n"
    grain = """.slide::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.06;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}""" if th["grain"] else ""
    return f"""{font_faces()}
{bgs}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#777;font-family:Inter,sans-serif}}
.slide{{width:1080px;height:1350px;position:relative;overflow:hidden;padding:100px 88px 0;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);margin-bottom:30px}}
{grain}
.kicker{{font-size:26px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}}
.h{{font-family:{th['head_font']};font-weight:{th['head_weight']};text-transform:{th['head_case']};letter-spacing:{th['head_track']};line-height:{th['lh']}}}
.h em{{font-family:{th['accent_font']};font-style:{th['accent_style']};font-weight:{'400' if th['accent_font']=='Instrument' else 'inherit'};color:var(--acc);letter-spacing:-0.01em}}
s{{text-decoration-thickness:6px;text-decoration-color:var(--acc);opacity:.7}}
.body{{font-size:42px;line-height:1.42;color:var(--muted);margin-top:44px;max-width:860px}}
.body em{{font-style:normal;color:var(--ink);font-weight:600}}
.foot{{position:absolute;left:88px;right:88px;bottom:66px;display:flex;justify-content:space-between;align-items:center;font-size:25px;color:var(--muted)}}
.mark{{font-family:{th['head_font']};font-weight:{700 if t=='nexloop' else 600};font-size:{30 if t=='nexloop' else 34}px;letter-spacing:{'-0.02em' if t=='nexloop' else '-0.01em'};color:var(--ink)}}
.mark i{{font-family:{th['accent_font']};font-style:{th['accent_style']};font-weight:400;color:var(--acc)}}
/* cover */
.cover .h{{font-size:{150 if t=='tapmore' else 124}px;margin-top:{150 if t=='tapmore' else 120}px}}
.cover .sub{{font-size:40px;line-height:1.4;color:var(--muted);margin-top:50px;max-width:800px}}
.swipe{{position:absolute;right:88px;bottom:150px;display:flex;align-items:center;gap:18px;font-size:30px;color:var(--ink);opacity:.8}}
.swipe span{{display:inline-block;width:90px;height:2px;background:currentColor;position:relative}}
.swipe span::after{{content:"";position:absolute;right:0;top:-8px;width:16px;height:16px;border-top:2px solid;border-right:2px solid;transform:rotate(45deg)}}
/* text */
.text .h{{font-size:{120 if t=='tapmore' else 112}px;margin-top:160px}}
/* stat */
.stat .num{{font-family:{th['head_font']};font-weight:{th['head_weight']};font-size:380px;line-height:.85;letter-spacing:-.06em;color:var(--acc);margin-top:90px}}
.stat .h{{font-size:{92 if t=='tapmore' else 84}px;margin-top:40px}}
.stat .src{{position:absolute;left:88px;bottom:140px;font-size:22px;color:var(--muted);opacity:.8}}
/* list */
.list .h,.steps .h,.grid .h,.compare .h{{font-size:{96 if t=='tapmore' else 88}px;margin-top:30px}}
.items{{margin-top:56px}}
.item{{display:flex;gap:40px;align-items:baseline;padding:30px 0;border-top:2px solid var(--line)}}
.item:last-child{{border-bottom:2px solid var(--line)}}
.item .n{{font-family:{th['accent_font'] if t=='tapmore' else 'Inter'};font-style:{th['accent_style']};font-weight:{400 if t=='tapmore' else 800};font-size:{58 if t=='tapmore' else 40}px;color:var(--acc);width:70px;flex:none}}
.item .t{{font-size:42px;line-height:1.28;font-weight:{500 if t=='tapmore' else 600}}}
.item .t small{{display:block;font-size:30px;color:var(--muted);font-weight:400;margin-top:8px}}
/* steps */
.stepsbox{{margin-top:80px;display:flex;flex-direction:column;gap:56px}}
.step{{display:flex;gap:40px;align-items:flex-start}}
.step .dot{{flex:none;width:84px;height:84px;border-radius:50%;border:2px solid var(--ink);display:grid;place-items:center;font-family:{th['head_font']};font-weight:{th['head_weight'] if t=='tapmore' else 800};font-size:38px}}
.step b{{display:block;font-size:46px;font-weight:600;letter-spacing:-.01em}}
.step span{{display:block;font-size:32px;color:var(--muted);margin-top:10px;line-height:1.4}}
/* grid */
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:64px}}
.card{{background:var(--card);border-radius:{36 if t=='tapmore' else 20}px;padding:42px 38px;height:340px;display:flex;flex-direction:column}}
.card svg{{width:62px;height:62px;stroke:var(--acc);fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}}
.card b{{font-family:{'Fraunces' if t=='tapmore' else 'Inter'};font-weight:{400 if t=='tapmore' else 700};font-size:{44 if t=='tapmore' else 40}px;letter-spacing:-.02em;line-height:1.1;margin-top:auto}}
.card span{{font-size:26px;color:var(--muted);line-height:1.4;margin-top:12px}}
/* compare */
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:64px}}
.col{{border-radius:{36 if t=='tapmore' else 20}px;padding:44px 38px;background:var(--card)}}
.col.new{{background:var(--ink);color:var(--bg)}}
.col .lab{{font-size:24px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;opacity:.6;margin-bottom:26px}}
.col p{{font-size:34px;line-height:1.3;padding:18px 0;border-top:1.5px solid color-mix(in srgb,currentColor 18%,transparent)}}
.col.old p{{color:var(--muted)}}
/* phone */
.phone .h{{font-size:{104 if t=='tapmore' else 92}px;margin-top:20px;max-width:560px}}
.phone .note{{position:absolute;left:88px;bottom:190px;font-size:32px;line-height:1.45;max-width:400px;color:var(--muted)}}
.dev{{position:absolute;right:30px;bottom:-190px;width:520px;height:1060px;border-radius:72px;background:#1E1916;padding:18px;transform:rotate(-6deg);box-shadow:0 60px 80px rgba(0,0,0,.25)}}
.scr{{width:100%;height:100%;border-radius:56px;background:#FBF7F0;color:#1E1916;padding:70px 34px 0;overflow:hidden;font-family:Inter}}
.notch{{position:absolute;top:34px;left:50%;transform:translateX(-50%);width:130px;height:34px;border-radius:20px;background:#1E1916}}
.pn{{display:flex;align-items:center;gap:18px}}
.pl{{width:72px;height:72px;border-radius:50%;background:#3F5B4C;color:#FBF7F0;display:grid;place-items:center;font-family:Fraunces;font-size:38px}}
.pn b{{font-family:Fraunces;font-weight:600;font-size:32px;display:block}}
.pn span{{font-size:20px;color:#7A6D63}}
.tile{{margin-top:20px;border-radius:26px;padding:24px 26px;background:#F3ECE1;font-size:24px}}
.tile .lab{{font-size:17px;letter-spacing:.14em;text-transform:uppercase;color:#7A6D63;font-weight:600;margin-bottom:12px}}
.stamps{{display:flex;gap:10px}}
.stamps i{{width:40px;height:40px;border-radius:50%;border:2.5px solid #C4572F}}
.stamps i.on{{background:#C4572F}}
.row{{display:flex;justify-content:space-between;align-items:center}}
.pill{{background:#1E1916;color:#FBF7F0;border-radius:40px;padding:10px 20px;font-size:19px;font-weight:600}}
.ml{{display:flex;justify-content:space-between;padding:8px 0;font-size:23px}}
.ml span:last-child{{font-weight:600}}
.bub{{max-width:80%;padding:16px 20px;border-radius:22px;font-size:22px;line-height:1.35;margin-top:12px}}
.bub.in{{background:#fff}}
.bub.out{{background:#DCF3D6;margin-left:auto}}
/* cta */
.cta .h{{font-size:{140 if t=='tapmore' else 132}px;margin-top:110px}}
.cta .sub{{font-size:52px;margin-top:30px;color:var(--acc);font-family:{th['accent_font']};font-style:{th['accent_style']};font-weight:{400 if t=='tapmore' else 600}}}
.chips{{display:flex;gap:16px;margin-top:56px;flex-wrap:wrap}}
.chips span{{border:2px solid color-mix(in srgb,var(--ink) 30%,transparent);border-radius:60px;padding:16px 30px;font-size:28px}}
.qrbox{{position:absolute;left:88px;bottom:170px;display:flex;align-items:center;gap:40px}}
.qr{{width:210px;height:210px;background:#fff;border-radius:{28 if t=='tapmore' else 16}px;padding:22px}}
.qr svg{{width:100%;height:100%}}
.qrbox b{{font-family:{th['head_font']};font-weight:{400 if t=='tapmore' else 800};font-size:60px;display:block;letter-spacing:-.02em}}
.qrbox span{{font-size:30px;color:var(--muted)}}
"""

# ---------------------------------------------------------------- slides
def phone_screen(sc):
    rows = []
    for r in sc.get("rows", []):
        k = r.get("kind")
        if k == "stamps":
            on, of = r.get("on", 6), r.get("of", 8)
            dots = "".join(f'<i class="{"on" if i < on else ""}"></i>' for i in range(of))
            rows.append(f'<div class="tile"><div class="lab">Your stamp card</div><div class="stamps">{dots}</div>'
                        f'<div style="margin-top:12px;font-size:21px;color:#7A6D63">{html.escape(r.get("label",""))}</div></div>')
        elif k == "wifi":
            rows.append(f'<div class="tile"><div class="row"><div><div class="lab" style="margin:0">Wi-Fi</div>'
                        f'<div style="margin-top:6px">{html.escape(r.get("ssid","Guest"))}</div></div><div class="pill">Copy</div></div></div>')
        elif k == "menu":
            lines = "".join(f'<div class="ml"><span>{html.escape(a)}</span><span>{html.escape(b)}</span></div>' for a, b in r.get("items", []))
            lab = html.escape(r.get("label", "Today's menu"))
            rows.append(f'<div class="tile"><div class="lab">{lab}</div>{lines}</div>')
        elif k == "rating":
            rows.append(f'<div class="tile"><div class="row"><div>{html.escape(r.get("label","How was your visit?"))}</div>'
                        f'<div style="color:#C4572F;font-size:28px">★★★★★</div></div></div>')
        elif k == "chat":
            b = "".join(f'<div class="bub {d}">{html.escape(m)}</div>' for d, m in r.get("msgs", []))
            rows.append(f'<div class="tile" style="background:#EFE7DB">{b}</div>')
    initial = (sc.get("name") or "B")[0]
    return (f'<div class="dev"><div class="notch"></div><div class="scr"><div class="pn"><div class="pl">{html.escape(initial)}</div>'
            f'<div><b>{html.escape(sc.get("name","Your café"))}</b><span>{html.escape(sc.get("tagline",""))}</span></div></div>'
            + "".join(rows) + "</div></div>")

def slide_html(i, s, theme, handle, n):
    t = s.get("type", "text")
    bg = s.get("bg") or ("dark" if t in ("cover", "cta") else ("light" if i % 2 else "alt"))
    k = f'<div class="kicker">{md(s.get("kicker",""))}</div>' if s.get("kicker") else ""
    inner = ""
    if t == "cover":
        inner = k + f'<div class="h">{md(s["title"])}</div>' + (f'<div class="sub">{md(s["sub"])}</div>' if s.get("sub") else "") + '<div class="swipe">Swipe <span></span></div>'
    elif t == "text":
        inner = k + f'<div class="h">{md(s["title"])}</div>' + (f'<div class="body">{md(s.get("body",""))}</div>' if s.get("body") else "")
    elif t == "stat":
        inner = k + f'<div class="num">{md(s["number"])}</div><div class="h">{md(s.get("title",""))}</div>' \
                + (f'<div class="body">{md(s.get("body",""))}</div>' if s.get("body") else "") \
                + f'<div class="src">{md(s.get("source",""))}</div>'
    elif t == "list":
        its = "".join(f'<div class="item"><div class="n">{j+1:02d}</div><div class="t">{md(x["t"])}'
                      + (f'<small>{md(x["s"])}</small>' if x.get("s") else "") + '</div></div>'
                      for j, x in enumerate(s.get("items", [])))
        inner = k + f'<div class="h">{md(s["title"])}</div><div class="items">{its}</div>'
    elif t == "steps":
        st = "".join(f'<div class="step"><div class="dot">{j+1}</div><div><b>{md(x["t"])}</b>'
                     + (f'<span>{md(x["s"])}</span>' if x.get("s") else "") + '</div></div>'
                     for j, x in enumerate(s.get("steps", [])))
        inner = k + f'<div class="h">{md(s["title"])}</div><div class="stepsbox">{st}</div>'
    elif t == "grid":
        cs = "".join(f'<div class="card"><svg viewBox="0 0 48 48">{ICONS.get(c.get("icon","bolt"), ICONS["bolt"])}</svg>'
                     f'<b>{md(c["t"])}</b><span>{md(c.get("s",""))}</span></div>' for c in s.get("cards", []))
        inner = k + f'<div class="h">{md(s["title"])}</div><div class="cards">{cs}</div>'
    elif t == "compare":
        L, R = s.get("left", {}), s.get("right", {})
        col = lambda d, c: f'<div class="col {c}"><div class="lab">{md(d.get("label",""))}</div>' + "".join(f"<p>{md(x)}</p>" for x in d.get("items", [])) + "</div>"
        inner = k + f'<div class="h">{md(s["title"])}</div><div class="cols">{col(L,"old")}{col(R,"new")}</div>'
    elif t == "phone":
        inner = k + f'<div class="h">{md(s["title"])}</div><p class="note">{md(s.get("body",""))}</p>' + phone_screen(s.get("screen", {}))
    elif t == "cta":
        chips = "".join(f"<span>{md(c)}</span>" for c in s.get("chips", []))
        qr = ""
        if s.get("qr"):
            th = THEMES[theme]["light"][1]
            qr = f'<div class="qrbox"><div class="qr">{qr_svg(s["qr"], th)}</div><div><b>{md(s.get("link",""))}</b><span>{md(s.get("link_sub","Scan, or tap the link in bio"))}</span></div></div>'
        inner = k + f'<div class="h">{md(s["title"])}</div>' + (f'<div class="sub">{md(s.get("sub",""))}</div>' if s.get("sub") else "") + (f'<div class="chips">{chips}</div>' if chips else "") + qr
    show_handle = t in ("cover", "cta")
    foot = f'<div class="foot"><div class="mark">{THEMES[theme]["wordmark"]}</div><div>{html.escape(handle) if show_handle else ""}</div></div>'
    return f'<section class="slide {t} bg-{bg}" id="s{i+1}">{inner}{foot}</section>'

# ---------------------------------------------------------------- checks
def lint(spec):
    w = []
    sl = spec["slides"]
    if not 5 <= len(sl) <= 20:
        w.append(f"{len(sl)} slides: aim for 6-10 (Instagram max 20)")
    for i, s in enumerate(sl, 1):
        t = s.get("type")
        if not s.get("alt"):
            w.append(f"slide {i}: missing alt text")
        if t == "cover" and words(s.get("title")) > 10:
            w.append(f"slide {i}: cover title has {words(s.get('title'))} words (max 8-10)")
        if words(s.get("title")) > 12 and t != "cover":
            w.append(f"slide {i}: headline has {words(s.get('title'))} words (aim for 8)")
        if words(s.get("body")) > 45:
            w.append(f"slide {i}: body has {words(s.get('body'))} words (max 30-45)")
        if t == "stat" and not s.get("source"):
            w.append(f"slide {i}: stat without a source; add one or write 'Illustrative example'")
        if t == "list" and len(s.get("items", [])) > 5:
            w.append(f"slide {i}: more than 5 list items; split the slide")
        if t == "grid" and len(s.get("cards", [])) != 4:
            w.append(f"slide {i}: grid needs exactly 4 cards")
        if len(re.findall(r"\*(.+?)\*", json.dumps(s))) > 3:
            w.append(f"slide {i}: more than 3 accented phrases")
    return w

def find_chrome():
    for pat in ("/opt/pw-browsers/*/chrome-linux*/chrome", os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None

async def shoot(doc_path, n, out):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        exe = find_chrome()
        b = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        await pg.goto("file://" + doc_path)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(400)
        # Auto-fit: shrink a headline (never below 80% of its size) until the slide's text clears the footer.
        await pg.evaluate("""() => document.querySelectorAll('.slide').forEach(s => {
            const h = s.querySelector('.h'); if (!h) return;
            const r = s.getBoundingClientRect(); const start = parseFloat(getComputedStyle(h).fontSize);
            const low = () => Math.max(...[...s.querySelectorAll('.h,.sub,.body,.items,.stepsbox,.cards,.cols,.chips')]
                         .map(e => e.getBoundingClientRect().bottom));
            const limit = r.bottom - (s.querySelector('.swipe,.qrbox,.src,.note') ? 260 : 130);
            let f = start; while (low() > limit && f > start * 0.8) { f -= 4; h.style.fontSize = f + 'px'; }
        })""")
        overflow = await pg.evaluate("""() => [...document.querySelectorAll('.slide')].map(s => {
            const r = s.getBoundingClientRect(); const bad = [];
            s.querySelectorAll('.h,.body,.items,.stepsbox,.cards,.cols,.chips,.sub,.qrbox').forEach(e => {
              const q = e.getBoundingClientRect();
              if (q.bottom > r.bottom - 110 || q.right > r.right - 40) bad.push(e.className);
            }); return bad; })""")
        for i in range(1, n + 1):
            await pg.locator(f"#s{i}").screenshot(path=os.path.join(out, f"_s{i}.png"))
        await b.close()
    return overflow

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    theme = spec.get("theme", "tapmore")
    handle = spec.get("handle", "@nexloop.io")
    os.makedirs(a.out, exist_ok=True)
    out = os.path.abspath(a.out)
    slides = spec["slides"]
    body = "".join(slide_html(i, s, theme, handle, len(slides)) for i, s in enumerate(slides))
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{css(theme)}</style></head><body>{body}</body></html>"
    doc_path = os.path.join(out, "slides.html")
    open(doc_path, "w").write(doc)
    overflow = asyncio.run(shoot(doc_path, len(slides), out))
    from PIL import Image
    files = []
    for i in range(1, len(slides) + 1):
        src = os.path.join(out, f"_s{i}.png")
        im = Image.open(src).convert("RGB")
        dst = os.path.join(out, f"slide_{i:02d}.jpg")
        im.save(dst, "JPEG", quality=90, optimize=True, progressive=True)
        os.remove(src)
        files.append(dst)
    w, h = 270, 338
    sheet = Image.new("RGB", (len(files) * (w + 10) - 10, h), (120, 120, 120))
    for i, f in enumerate(files):
        sheet.paste(Image.open(f).resize((w, h)), (i * (w + 10), 0))
    sheet.save(os.path.join(out, "contact.png"))
    warns = lint(spec)
    for i, bad in enumerate(overflow, 1):
        if bad:
            warns.append(f"slide {i}: content runs into the footer or edge ({', '.join(bad)}); cut words or split")
    man = {"theme": theme, "files": [os.path.basename(f) for f in files],
           "bytes": [os.path.getsize(f) for f in files],
           "alt": [s.get("alt", "") for s in slides], "warnings": warns}
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=2, ensure_ascii=False)
    print(json.dumps(man, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
