import os, re, html, json, base64, asyncio, subprocess, urllib.request, urllib.parse
from pathlib import Path

try:
    import edge_tts
except Exception:
    edge_tts = None
try:
    from midiutil import MIDIFile
except Exception:
    MIDIFile = None

UA = {"User-Agent": "Mozilla/5.0 (KMS CART video maker)"}
STORE = "https://kmscart.com"


def get(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def jget(url, timeout=20):
    return json.loads(get(url, timeout).decode())


title = os.environ.get("TITLE", "Smart Deal").strip()[:80]
caption = os.environ.get("CAPTION", "").strip()
img_url = os.environ.get("IMG", "").strip()
tts_key = os.environ.get("TTS_KEY", "").strip()
pix_key = os.environ.get("PIX_KEY", "").strip()
run_num = int(os.environ.get("GITHUB_RUN_NUMBER", "1") or 1)
tl = title.lower()

# ---------- 1. Product data from the live store (price, MRP, extra photos) ----------
price = compare = None
images = []
try:
    q = urllib.parse.quote(title[:60])
    s = jget(f"{STORE}/search/suggest.json?q={q}&resources[type]=product&resources[limit]=1")
    prods = s.get("resources", {}).get("results", {}).get("products", [])
    if prods:
        p = prods[0]
        price = float(p.get("price") or 0) or None
        compare = float(p.get("compare_at_price_max") or 0) or None
        handle = p.get("handle")
        if handle:
            full = jget(f"{STORE}/products/{handle}.json").get("product", {})
            images = [i.get("src") for i in full.get("images", []) if i.get("src")]
except Exception as e:
    print("Store lookup skipped:", e)
try:
    price = price or float(os.environ.get("PRICE") or 0) or None
    compare = compare or float(os.environ.get("MRP") or 0) or None
except ValueError:
    pass
if img_url and img_url not in images:
    images.insert(0, img_url)
images = images[:4] or ([img_url] if img_url else [])

photos = []
for n, u in enumerate(images):
    try:
        Path(f"p{n}.jpg").write_bytes(get(u, 30))
        photos.append(f"p{n}.jpg")
    except Exception as e:
        print("Image skipped:", e)
if not photos:
    raise SystemExit("No product image could be downloaded")

def rupee(v):
    return "₹" + (f"{v:,.0f}" if v else "")

disc = None
if price and compare and compare > price:
    disc = int(round((compare - price) * 100 / compare))

# ---------- 2. Language rotation: English -> Hindi -> Malayalam ----------
clean = re.sub(r"[*#_`]", "", caption)
parts = [re.sub(r"^(Malayalam|Hindi|English)\s*[:\-–]\s*", "", l.strip(), flags=re.I)
         for l in re.split(r"[\n.!?]+", clean)]
def first(pattern, exclude=None, default=""):
    for l in parts:
        if len(l) > 6 and re.search(pattern, l) and not (exclude and re.search(exclude, l)):
            return l[:95]
    return default

lang_cycle = ["en", "hi", "ml"]
LANG = lang_cycle[run_num % 3]
price_en = f" Just {rupee(price)} only." if price else ""
price_hi = f" सिर्फ़ {rupee(price)} में।" if price else ""
price_ml = f" വെറും {rupee(price)} മാത്രം." if price else ""
if LANG == "hi":
    line = first(r"[ऀ-ॿ]", default="भारत में ट्रेंडिंग स्मार्ट डील")
    spoken = f"{line}.{price_hi} अभी ऑर्डर करें kmscart dot com पर! कैश ऑन डिलीवरी उपलब्ध है।"
    sub = line
    gvoice, evoice, glang, font = "hi-IN-Wavenet-A", "hi-IN-SwaraNeural", "hi-IN", "Noto Sans Devanagari"
elif LANG == "ml":
    line = first(r"[ഀ-ൿ]", default=f"{title} ഇപ്പോൾ KMS CART-ൽ")
    spoken = f"{line}.{price_ml} ഇപ്പോൾ തന്നെ kmscart dot com-ൽ ഓർഡർ ചെയ്യൂ! ക്യാഷ് ഓൺ ഡെലിവറി ലഭ്യമാണ്."
    sub = line
    gvoice, evoice, glang, font = "ml-IN-Wavenet-A", "ml-IN-SobhanaNeural", "ml-IN", "Noto Sans Malayalam"
else:
    line = first(r"[A-Za-z]", exclude=r"[ഀ-ൿऀ-ॿ]", default=f"Upgrade your everyday with {title}")
    spoken = f"{line}.{price_en} Order now at kmscart dot com! Cash on Delivery available."
    sub = line
    gvoice, evoice, glang, font = "en-IN-Wavenet-D", "en-IN-NeerjaExpressiveNeural", "en-IN", "Noto Sans"

# ---------- 3. Voice (Google TTS key if present, else free Edge TTS) ----------
tts_ok = False
if tts_key:
    try:
        body = json.dumps({"input": {"text": spoken}, "voice": {"languageCode": glang, "name": gvoice},
                           "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.03}}).encode()
        req = urllib.request.Request(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={tts_key}",
                                     data=body, headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
        if "audioContent" in res:
            Path("voice.mp3").write_bytes(base64.b64decode(res["audioContent"]))
            tts_ok = True
    except Exception as e:
        print("Google TTS fallback:", e)
if not tts_ok and edge_tts:
    try:
        asyncio.run(edge_tts.Communicate(spoken, evoice, rate="+4%").save("voice.mp3"))
        tts_ok = True
    except Exception as e:
        print("Edge TTS failed:", e)

dur = 14.0
if tts_ok and Path("voice.mp3").exists():
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=noprint_wrappers=1:nokey=1", "voice.mp3"]).decode().strip()
    dur = max(10.0, min(20.0, float(out) + 1.5))
else:
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1", "voice.mp3"], check=True)

# ---------- 4. Background music (generated, royalty free) ----------
if MIDIFile:
    m = MIDIFile(2)
    m.addTempo(0, 0, 104); m.addProgramChange(0, 0, 0, 12)
    m.addTempo(1, 0, 104); m.addProgramChange(1, 1, 0, 89)
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 67]]
    for bar in range(12):
        c = chords[bar % 4]
        for n in c: m.addNote(1, 1, n, bar * 4, 4, 55)
        for st, n in enumerate(c * 2): m.addNote(0, 0, n + 12, bar * 4 + st * 0.5, 0.45, 85)
    with open("bgm.mid", "wb") as f: m.writeFile(f)

# ---------- 5. Pixabay real-life b-roll (optional) ----------
q = "modern home lifestyle"
if any(w in tl for w in ["car", "bike", "tyre", "windshield", "vacuum"]): q = "car driving clean"
elif any(w in tl for w in ["kitchen", "jug", "tumbler", "chopper", "bottle", "mug", "cleaner", "dish"]): q = "modern kitchen cooking"
elif any(w in tl for w in ["baby", "kid", "toy", "toothbrush", "puzzle"]): q = "happy family kids home"
elif any(w in tl for w in ["pet", "dog", "cat"]): q = "cute dog cat home"
elif any(w in tl for w in ["makeup", "lipstick", "cosmetic", "shoe", "watch", "bag"]): q = "fashion lifestyle beauty"
if pix_key:
    try:
        d = jget(f"https://pixabay.com/api/videos/?key={pix_key}&q={urllib.parse.quote(q)}&per_page=10&safesearch=true", 15)
        hits = d.get("hits", [])
        if hits:
            v = hits[run_num % len(hits)].get("videos", {})
            vurl = (v.get("medium") or v.get("small") or {}).get("url")
            if vurl: Path("bg_video.mp4").write_bytes(get(vurl, 60))
    except Exception as e:
        print("Pixabay skipped:", e)

# ---------- 6. Karaoke subtitles in the SAME language as the voice ----------
words = sub.split()
per_w = max(25, int(((dur - 1.8) * 100) / max(1, len(words))))
k_line = "".join(f"{{\\k{per_w}}}{w} " for w in words)
Path("subs.ass").write_text(f"""[Script Info]
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},54,&H0000E5FF,&H00FFFFFF,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,3,4,0,2,60,60,600,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.20,0:00:{dur-0.3:05.2f},Default,,0,0,0,,{k_line}
""", encoding="utf-8")

# ---------- 7. Overlay (video) + premium poster (feed image) ----------
themes = [("#0f172a", "#1e293b", "#f59e0b", "#111827", "🔥 TRENDING IN INDIA"),
          ("#7f1d1d", "#dc2626", "#fde047", "#111827", "⚡ DEAL OF THE DAY"),
          ("#0b1324", "#1d4ed8", "#38bdf8", "#082f49", "✨ BESTSELLER PICK")]
b1, b2, ac, at, tg = themes[run_num % 3]
t = html.escape(title)
price_html = ""
if price:
    price_html = f'<span class="pr">{rupee(price)}</span>'
    if disc: price_html += f'<span class="mrp">{rupee(compare)}</span><span class="off">{disc}% OFF</span>'

css_common = "*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Noto Sans','Poppins','DejaVu Sans',sans-serif,'Noto Color Emoji'}"
Path("overlay.html").write_text(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css_common}
body{{width:1080px;height:1920px;background:transparent;display:flex;flex-direction:column;justify-content:space-between;padding:56px 48px}}
.top{{display:flex;justify-content:space-between;align-items:center;background:rgba(15,23,42,.82);padding:20px 34px;border-radius:28px;border:2px solid rgba(255,255,255,.18)}}
.logo{{color:#fff;font-size:34px;font-weight:900;letter-spacing:2px}}.tag{{background:{ac};color:{at};font-size:26px;font-weight:900;padding:10px 26px;border-radius:999px}}
.card{{width:100%;background:linear-gradient(135deg,{b1},{b2});color:#fff;padding:32px 36px;border-radius:32px;text-align:center;border:2px solid rgba(255,255,255,.22);display:flex;flex-direction:column;gap:16px;align-items:center}}
.ti{{font-size:38px;font-weight:800}}.prw{{display:flex;gap:18px;align-items:center}}.pr{{font-size:58px;font-weight:900;color:{ac}}}.mrp{{font-size:32px;text-decoration:line-through;opacity:.7}}.off{{background:#16a34a;font-size:28px;font-weight:900;padding:6px 18px;border-radius:12px}}
.bs{{display:flex;gap:16px;flex-wrap:wrap;justify-content:center}}.bg{{background:rgba(255,255,255,.14);padding:10px 22px;border-radius:14px;font-size:26px;font-weight:700}}
.ct{{background:{ac};color:{at};font-size:34px;font-weight:900;padding:16px 44px;border-radius:999px}}</style></head><body>
<div class="top"><div class="logo">KMS CART</div><div class="tag">{tg}</div></div>
<div class="card"><div class="ti">{t}</div><div class="prw">{price_html}</div>
<div class="bs"><div class="bg">💵 Cash on Delivery</div><div class="bg">🚚 Free Pan-India Delivery</div></div>
<div class="ct">🛒 Order Now: www.kmscart.com</div></div></body></html>""", encoding="utf-8")

prod_src = Path(photos[0]).resolve().as_uri()
Path("poster.html").write_text(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css_common}
body{{width:1080px;height:1350px;overflow:hidden;background:radial-gradient(circle at 70% 25%,{b2} 0%,{b1} 60%,#020617 100%);color:#fff;position:relative}}
.glow{{position:absolute;width:760px;height:760px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.22),transparent 65%);left:160px;top:170px}}
.hdr{{position:absolute;top:44px;left:48px;right:48px;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-size:40px;font-weight:900;letter-spacing:3px}}.logo b{{color:{ac}}}
.tag{{background:{ac};color:{at};font-size:26px;font-weight:900;padding:12px 26px;border-radius:999px}}
.ph{{position:absolute;left:150px;top:150px;width:780px;height:640px;background:#fff;border-radius:44px;box-shadow:0 40px 90px rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;overflow:hidden}}
.ph img{{max-width:92%;max-height:92%;object-fit:contain}}
.disc{{position:absolute;right:110px;top:120px;width:190px;height:190px;border-radius:50%;background:#16a34a;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:900;font-size:56px;line-height:1;box-shadow:0 12px 30px rgba(0,0,0,.4);border:6px solid #fff;transform:rotate(-10deg)}}
.disc small{{font-size:28px}}
.ti{{position:absolute;left:60px;right:60px;top:820px;text-align:center;font-size:52px;font-weight:900;line-height:1.15}}
.prw{{position:absolute;left:0;right:0;top:960px;display:flex;justify-content:center;align-items:baseline;gap:22px}}
.pr{{font-size:92px;font-weight:900;color:{ac}}}.mrp{{font-size:44px;text-decoration:line-through;opacity:.7}}.off{{display:none}}
.bs{{position:absolute;left:0;right:0;top:1100px;display:flex;justify-content:center;gap:18px}}
.bg{{background:rgba(255,255,255,.14);border:2px solid rgba(255,255,255,.25);padding:12px 24px;border-radius:16px;font-size:28px;font-weight:700}}
.ft{{position:absolute;left:0;right:0;bottom:0;height:120px;background:{ac};color:{at};display:flex;align-items:center;justify-content:center;font-size:44px;font-weight:900;letter-spacing:1px}}
</style></head><body><div class="glow"></div>
<div class="hdr"><div class="logo">KMS <b>CART</b></div><div class="tag">{tg}</div></div>
<div class="ph"><img src="{prod_src}"></div>
{f'<div class="disc">{disc}%<small>OFF</small></div>' if disc else ''}
<div class="ti">{t}</div><div class="prw">{price_html}</div>
<div class="bs"><div class="bg">💵 Cash on Delivery</div><div class="bg">🚚 Free Delivery</div><div class="bg">✅ Easy Order</div></div>
<div class="ft">🛒 Order now · www.kmscart.com</div></body></html>""", encoding="utf-8")

Path("dur.txt").write_text(f"{dur:.1f}")
Path("photos.txt").write_text("\n".join(photos))
print("LANG", LANG, "price", price, "compare", compare, "photos", len(photos), "dur", dur)

# ---------- 8. Product slideshow clip (all store photos, soft zoom + crossfade) ----------
S = 920 if not Path("bg_video.mp4").exists() else 680
n = len(photos)
seg = max(2.5, dur / n + (0.6 if n > 1 else 0))
frames = int(seg * 30)
clips = []
for i, ph in enumerate(photos):
    out = f"c{i}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", ph, "-vf",
                    f"scale={S-40}:{S-40}:force_original_aspect_ratio=decrease:flags=lanczos,"
                    f"pad={S}:{S}:(ow-iw)/2:(oh-ih)/2:color=white,"
                    f"zoompan=z='min(zoom+0.0010,1.10)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={S}x{S}:fps=30",
                    "-t", f"{seg:.2f}", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", out],
                   check=True, capture_output=True)
    clips.append(out)
if n == 1:
    Path(clips[0]).rename("fg.mp4")
else:
    inputs, fc, prev, off = [], "", "[0:v]", 0.0
    for c in clips: inputs += ["-i", c]
    for i in range(1, n):
        off += seg - 0.6
        lab = f"[x{i}]" if i < n - 1 else "[out]"
        fc += f"{prev}[{i}:v]xfade=transition=fade:duration=0.6:offset={off:.2f}{lab};"
        prev = lab
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", fc.rstrip(";"), "-map", "[out]",
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "fg.mp4"], check=True, capture_output=True)
Path("fgsize.txt").write_text(str(S))
print("slideshow ready", n, "photos")
