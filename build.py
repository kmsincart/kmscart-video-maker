"""KMS CART ad maker v3 - motion-graphics video (no voice) + premium poster.
Runs in GitHub Actions. Inputs via env: IMG, TITLE, PRICE, MRP, GITHUB_RUN_NUMBER."""
import os, re, json, html, wave, asyncio, subprocess, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
from playwright.async_api import async_playwright

UA = {"User-Agent": "Mozilla/5.0 (KMS CART ad maker)"}
STORE = "https://kmscart.com"
FPS, DUR = 30, 12
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")


def get(url, t=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read()


title = re.sub(r"\s+", " ", os.environ.get("TITLE", "Smart Deal")).strip()[:90]
img_url = os.environ.get("IMG", "").strip()
run = int(os.environ.get("GITHUB_RUN_NUMBER", "1") or 1)

# ---------- product data from the live store ----------
price = compare = None
images = []
try:
    q = urllib.parse.quote(title[:60])
    s = json.loads(get(f"{STORE}/search/suggest.json?q={q}&resources[type]=product&resources[limit]=1"))
    ps = s.get("resources", {}).get("results", {}).get("products", [])
    if ps:
        p = ps[0]
        price = float(p.get("price") or 0) or None
        compare = float(p.get("compare_at_price_max") or 0) or None
        if p.get("handle"):
            full = json.loads(get(f"{STORE}/products/{p['handle']}.json")).get("product", {})
            images = [i["src"] for i in full.get("images", []) if i.get("src")]
except Exception as e:
    print("store lookup skipped:", e)
try:
    price = price or float(os.environ.get("PRICE") or 0) or None
    compare = compare or float(os.environ.get("MRP") or 0) or None
except ValueError:
    pass
if img_url and img_url not in images:
    images.insert(0, img_url)
photos = []
for n, u in enumerate(images[:3]):
    try:
        if u.startswith("file://"):
            Path(f"p{n}.jpg").write_bytes(Path(u[7:]).read_bytes())
        else:
            sep = "&" if "?" in u else "?"
            Path(f"p{n}.jpg").write_bytes(get(u + (sep + "width=900" if "cdn.shopify" in u else "")))
        photos.append(Path(f"p{n}.jpg").resolve().as_uri())
    except Exception as e:
        print("image skipped:", e)
if not photos:
    raise SystemExit("no product image")
disc = int(round((compare - price) * 100 / compare)) if price and compare and compare > price else None

# ---------- copy (safe, no invented claims) ----------
tl = title.lower()
hooks = {
    "drink": [("SIP", "IN STYLE"), ("STAY", "HYDRATED"), ("YOUR NEW", "FAVOURITE")],
    "kitchen": [("COOK", "SMARTER"), ("KITCHEN", "UPGRADE"), ("NO MORE", "MESS")],
    "car": [("DRIVE", "IN STYLE"), ("CAR", "UPGRADE"), ("ROAD", "READY")],
    "clean": [("CLEAN", "IN SECONDS"), ("SPARKLE", "MODE ON"), ("NO MORE", "SCRUBBING")],
    "kids": [("PLAY.", "LEARN. GROW."), ("KIDS", "LOVE IT"), ("SMART", "PLAYTIME")],
    "pet": [("HAPPY", "PETS"), ("PET", "PARENTS ❤"), ("FUR", "FREE HOME")],
    "fit": [("GET", "STRONGER"), ("NO GYM?", "NO PROBLEM"), ("DAILY", "FIT")],
    "home": [("SMART", "FIND"), ("HOME", "UPGRADE"), ("DEAL", "OF THE DAY")],
}
cat = "home"
for k, words in {"drink": ["tumbler", "mug", "bottle", "jug", "sipper", "flask"],
                 "kitchen": ["kitchen", "chopper", "container", "opener", "chopstick", "dish"],
                 "car": ["car", "bike", "windshield", "dashboard", "helmet"],
                 "clean": ["clean", "descaler", "remover", "mop", "grout", "stain", "rust", "washing"],
                 "kids": ["kid", "baby", "puzzle", "copybook", "toy", "piggy", "spinner"],
                 "pet": ["pet", "dog", "cat"],
                 "fit": ["exerciser", "resistance", "grip", "gyro", "fitness"]}.items():
    if any(w in tl for w in words):
        cat = k
        break
h1, h2 = hooks[cat][run % 3]
parts = [x.strip(" -–|,") for x in re.split(r"\s[–|-]\s|\swith\s|\s\|\s|,", title) if x.strip(" -–|,")]
name = parts[0][:42]
chips = [x[:30] for x in parts[1:3]] + ["💵 Cash on Delivery", "🚚 Pan-India Delivery", "✅ Quality Checked"]
chips = chips[:3]
themes = [  # bg1, bg2, accent, accent2
    ("#3b1d8f", "#0b0f1f", "#ffd34d", "#ff8a00"),
    ("#8f1d3b", "#14070b", "#ffe08a", "#ff4d6d"),
    ("#0e5e6f", "#04141a", "#7cf7c8", "#22c55e"),
]
b1, b2, ac, ac2 = themes[run % 3]
rupee = lambda v: "₹" + f"{v:,.0f}" if v else ""
E = html.escape

# ---------- video HTML ----------
n = len(photos)
imgs = "".join(f'<img class="ph ph{i}" src="{u}">' for i, u in enumerate(photos))
ph_css = ""
if n > 1:
    seg = 30 / n  # photos rotate between 20% and 55% of the timeline
    for i in range(n):
        a, b = 20 + i * (35 / n), 20 + (i + 1) * (35 / n)
        ph_css += f".ph{i}{{animation:ph{i} 12s forwards}}@keyframes ph{i}{{0%,{max(0,a-2):.1f}%{{opacity:{1 if i==0 else 0}}}{a:.1f}%{{opacity:1}}{b:.1f}%{{opacity:1}}{b+2:.1f}%{{opacity:{1 if i==n-1 else 0}}}100%{{opacity:{1 if i==0 else 0}}}}}"
mrp_html = f'<div class="mrp">MRP {rupee(compare)}</div><div class="off">{disc}% OFF</div>' if disc else ""
price_html = f'<div class="lbl">ONLY</div><div class="amt">{rupee(price)}</div>{mrp_html}' if price else '<div class="amt" style="font-size:150px">BEST PRICE</div>'
video_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1920px;overflow:hidden;font-family:Poppins,'Noto Sans','Noto Sans Malayalam',sans-serif;background:{b2};color:#fff;position:relative}}
.bg{{position:absolute;inset:0;background:radial-gradient(circle at 50% 40%,{b1} 0%,{b2} 70%);animation:hue 12s linear forwards}}
@keyframes hue{{0%{{filter:hue-rotate(0)}}50%{{filter:hue-rotate(25deg)}}100%{{filter:hue-rotate(-20deg)}}}}
.ring{{position:absolute;left:50%;top:42%;border-radius:50%;border:3px solid rgba(255,255,255,.13);transform:translate(-50%,-50%) scale(0);animation:ring 12s ease-out forwards}}
.r1{{width:760px;height:760px;animation-delay:2s}}.r2{{width:960px;height:960px;animation-delay:2.15s}}.r3{{width:1160px;height:1160px;animation-delay:2.3s}}
@keyframes ring{{0%{{transform:translate(-50%,-50%) scale(0);opacity:0}}6%{{transform:translate(-50%,-50%) scale(1.05);opacity:1}}10%{{transform:translate(-50%,-50%) scale(1)}}100%{{transform:translate(-50%,-50%) scale(1.08);opacity:.6}}}}
.pp i{{position:absolute;border-radius:50%;background:{ac};opacity:0;animation:fly 12s linear forwards}}
@keyframes fly{{0%,16%{{opacity:0;transform:none}}20%{{opacity:.85}}100%{{opacity:0;transform:translateY(-900px)}}}}
.logo{{position:absolute;top:70px;left:0;right:0;text-align:center;font-weight:800;font-size:46px;letter-spacing:6px;animation:fade 12s forwards}}
.logo b{{color:{ac}}}@keyframes fade{{0%{{opacity:0;transform:translateY(-30px)}}4%{{opacity:1;transform:none}}100%{{opacity:1}}}}
.hook{{position:absolute;top:640px;left:40px;right:40px;text-align:center;font-weight:900;line-height:1.05}}
.hook span{{display:block;font-size:124px;opacity:0;animation:slam 12s forwards}}
.hook span:nth-child(2){{color:{ac};animation-name:slam2}}
@keyframes slam{{0%{{opacity:0;transform:scale(2.4)}}3%{{opacity:1;transform:scale(.95)}}4.5%{{transform:scale(1)}}14%{{opacity:1;transform:scale(1)}}17%{{opacity:0;transform:translateY(-200px) scale(.8)}}100%{{opacity:0}}}}
@keyframes slam2{{0%,5%{{opacity:0;transform:scale(2.4)}}8%{{opacity:1;transform:scale(.95)}}9.5%{{transform:scale(1)}}14%{{opacity:1}}17%{{opacity:0;transform:translateY(-200px) scale(.8)}}100%{{opacity:0}}}}
.prod{{position:absolute;left:50%;top:42%;width:720px;height:720px;transform:translate(-50%,-50%) translateY(1400px) rotate(-10deg);animation:prod 12s cubic-bezier(.2,.9,.2,1) forwards}}
@keyframes prod{{0%,16%{{transform:translate(-50%,-50%) translateY(1400px) rotate(-10deg)}}24%{{transform:translate(-50%,-50%) translateY(-20px) rotate(2deg)}}27%{{transform:translate(-50%,-50%) rotate(0)}}55%{{transform:translate(-50%,-50%) scale(1)}}60%{{transform:translate(-50%,-62%) scale(.78)}}100%{{transform:translate(-50%,-64%) scale(.76)}}}}
.glow{{position:absolute;inset:-140px;border-radius:50%;background:radial-gradient(circle,{ac}66,transparent 65%);animation:pulse 1s ease-in-out infinite alternate}}
@keyframes pulse{{from{{transform:scale(.92)}}to{{transform:scale(1.06)}}}}
.card{{position:absolute;inset:0;border-radius:56px;background:#fff;box-shadow:0 40px 100px rgba(0,0,0,.55);overflow:hidden}}
.ph{{position:absolute;inset:30px;width:calc(100% - 60px);height:calc(100% - 60px);object-fit:contain;opacity:0}}.ph0{{opacity:1}}
{ph_css}
.name{{position:absolute;left:60px;right:60px;top:1180px;text-align:center;font-size:54px;font-weight:800;line-height:1.15;opacity:0;animation:nm 12s forwards}}
@keyframes nm{{0%,25%{{opacity:0;transform:translateY(60px)}}29%{{opacity:1;transform:none}}54%{{opacity:1}}57%{{opacity:0}}100%{{opacity:0}}}}
.chip{{position:absolute;left:50%;padding:20px 38px;border-radius:999px;background:rgba(255,255,255,.13);border:2px solid rgba(255,255,255,.35);font-size:40px;font-weight:700;white-space:nowrap;opacity:0}}
.c0{{top:1340px;animation:ch0 12s forwards}}.c1{{top:1460px;animation:ch1 12s forwards}}.c2{{top:1580px;animation:ch2 12s forwards}}
@keyframes ch0{{0%,30%{{opacity:0;transform:translateX(-80%) scale(.6)}}34%{{opacity:1;transform:translateX(-50%) scale(1.06)}}36%{{transform:translateX(-50%) scale(1)}}54%{{opacity:1;transform:translateX(-50%)}}57%{{opacity:0;transform:translateX(-50%)}}100%{{opacity:0}}}}
@keyframes ch1{{0%,34%{{opacity:0;transform:translateX(-20%) scale(.6)}}38%{{opacity:1;transform:translateX(-50%) scale(1.06)}}40%{{transform:translateX(-50%) scale(1)}}54%{{opacity:1;transform:translateX(-50%)}}57%{{opacity:0;transform:translateX(-50%)}}100%{{opacity:0}}}}
@keyframes ch2{{0%,38%{{opacity:0;transform:translateX(-80%) scale(.6)}}42%{{opacity:1;transform:translateX(-50%) scale(1.06)}}44%{{transform:translateX(-50%) scale(1)}}54%{{opacity:1;transform:translateX(-50%)}}57%{{opacity:0;transform:translateX(-50%)}}100%{{opacity:0}}}}
.price{{position:absolute;left:0;right:0;top:1090px;text-align:center;opacity:0;animation:pr 12s forwards}}
.price .lbl{{font-size:52px;font-weight:600;letter-spacing:4px;opacity:.85}}
.price .amt{{font-size:220px;font-weight:900;color:{ac};line-height:1;text-shadow:0 0 60px {ac}99}}
.price .mrp{{display:inline-block;font-size:48px;opacity:.75;text-decoration:line-through;margin-top:10px}}
.price .off{{display:inline-block;margin-left:24px;background:#16a34a;padding:8px 26px;border-radius:14px;font-size:48px;font-weight:900;vertical-align:middle}}
@keyframes pr{{0%,57%{{opacity:0;transform:scale(3)}}61%{{opacity:1;transform:scale(.9)}}63%{{transform:scale(1.05)}}65%{{transform:scale(1)}}100%{{opacity:1}}}}
.badges{{position:absolute;left:0;right:0;top:1500px;display:flex;justify-content:center;gap:24px;opacity:0;animation:up 12s forwards}}
.badges div{{background:#16a34a;padding:18px 30px;border-radius:18px;font-size:36px;font-weight:700}}.badges div:last-child{{background:#2563eb}}
@keyframes up{{0%,66%{{opacity:0;transform:translateY(80px)}}70%{{opacity:1;transform:none}}100%{{opacity:1}}}}
.cta{{position:absolute;left:80px;right:80px;bottom:120px;height:150px;border-radius:999px;background:linear-gradient(90deg,{ac},{ac2});color:#111;display:flex;align-items:center;justify-content:center;font-size:56px;font-weight:900;opacity:0;animation:cta 12s forwards;box-shadow:0 20px 60px {ac2}88;overflow:hidden}}
@keyframes cta{{0%,74%{{opacity:0;transform:translateY(200px)}}78%{{opacity:1;transform:translateY(-10px)}}80%{{transform:none}}84%{{transform:scale(1.05)}}86%{{transform:scale(1)}}90%{{transform:scale(1.05)}}92%{{transform:scale(1)}}100%{{opacity:1}}}}
.cta:after{{content:"";position:absolute;top:0;bottom:0;width:140px;left:-200px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.8),transparent);transform:skewX(-20deg);animation:sh 12s forwards}}
@keyframes sh{{0%,80%{{left:-200px}}88%{{left:110%}}100%{{left:110%}}}}
.flash{{position:absolute;inset:0;background:#fff;opacity:0;animation:fl 12s forwards}}
@keyframes fl{{0%,16%{{opacity:0}}16.5%{{opacity:.7}}19%{{opacity:0}}57%{{opacity:0}}57.5%{{opacity:.6}}60%{{opacity:0}}100%{{opacity:0}}}}
</style></head><body>
<div class="bg"></div><div class="ring r1"></div><div class="ring r2"></div><div class="ring r3"></div><div class="pp" id="pp"></div>
<div class="logo">KMS <b>CART</b></div>
<div class="hook"><span>{E(h1)}</span><span>{E(h2)}</span></div>
<div class="prod"><div class="glow"></div><div class="card">{imgs}</div></div>
<div class="name">{E(name)}</div>
{''.join(f'<div class="chip c{i}">{E(c)}</div>' for i, c in enumerate(chips))}
<div class="flash"></div>
<div class="price">{price_html}</div>
<div class="badges"><div>💵 Cash on Delivery</div><div>🚚 Pan-India</div></div>
<div class="cta">🛒 ORDER NOW • kmscart.com</div>
<script>let s={run * 7919 % 9973};const r=()=>(s=(s*16807)%2147483647)/2147483647;
const pp=document.getElementById('pp');for(let i=0;i<26;i++){{const e=document.createElement('i');e.style.left=(r()*1040)+'px';e.style.top=(900+r()*900)+'px';e.style.animationDelay=(-r()*2)+'s';const z=4+r()*12;e.style.width=e.style.height=z+'px';pp.appendChild(e)}}</script>
</body></html>"""
Path("video.html").write_text(video_html, encoding="utf-8")

# ---------- poster HTML (1080x1350 feed) ----------
pmrp = f'<span class="mrp">{rupee(compare)}</span>' if disc else ""
poff = f'<div class="disc">{disc}%<small>OFF</small></div>' if disc else ""
poster_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1350px;overflow:hidden;font-family:Poppins,'Noto Sans',sans-serif;color:#fff;background:radial-gradient(circle at 50% 38%,{b1} 0%,{b2} 72%);position:relative}}
.ring{{position:absolute;left:50%;top:40%;border-radius:50%;border:3px solid rgba(255,255,255,.12);transform:translate(-50%,-50%)}}
.glow{{position:absolute;left:50%;top:40%;width:900px;height:900px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,{ac}55,transparent 62%)}}
.top{{position:absolute;top:44px;left:56px;right:56px;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-size:42px;font-weight:800;letter-spacing:5px}}.logo b{{color:{ac}}}
.tag{{background:{ac};color:#111;font-weight:800;font-size:28px;padding:12px 28px;border-radius:999px}}
.hook{{position:absolute;top:130px;left:0;right:0;text-align:center;font-weight:900;font-size:64px;letter-spacing:1px}}.hook b{{color:{ac}}}
.card{{position:absolute;left:50%;top:40%;width:640px;height:640px;transform:translate(-50%,-44%);background:#fff;border-radius:52px;box-shadow:0 40px 90px rgba(0,0,0,.5);overflow:hidden}}
.card img{{position:absolute;inset:28px;width:calc(100% - 56px);height:calc(100% - 56px);object-fit:contain}}
.disc{{position:absolute;right:120px;top:250px;width:200px;height:200px;border-radius:50%;background:#16a34a;border:7px solid #fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:900;font-size:62px;line-height:1;transform:rotate(-10deg);box-shadow:0 14px 34px rgba(0,0,0,.45)}}.disc small{{font-size:30px}}
.name{{position:absolute;left:60px;right:60px;top:905px;text-align:center;font-size:44px;font-weight:800;line-height:1.15}}
.prow{{position:absolute;left:0;right:0;top:1000px;display:flex;justify-content:center;align-items:baseline;gap:22px}}
.amt{{font-size:120px;font-weight:900;color:{ac};text-shadow:0 0 40px {ac}88}}.mrp{{font-size:46px;opacity:.7;text-decoration:line-through}}
.chips{{position:absolute;left:0;right:0;top:1150px;display:flex;justify-content:center;gap:16px}}
.chips div{{background:rgba(255,255,255,.13);border:2px solid rgba(255,255,255,.3);padding:12px 22px;border-radius:14px;font-size:27px;font-weight:700}}
.cta{{position:absolute;left:0;right:0;bottom:0;height:104px;background:linear-gradient(90deg,{ac},{ac2});color:#111;display:flex;align-items:center;justify-content:center;font-size:42px;font-weight:900}}
</style></head><body>
<div class="glow"></div><div class="ring" style="width:820px;height:820px"></div><div class="ring" style="width:1040px;height:1040px"></div>
<div class="top"><div class="logo">KMS <b>CART</b></div><div class="tag">{'🔥 TRENDING' if run % 2 else '⚡ DEAL OF THE DAY'}</div></div>
<div class="hook">{E(h1)} <b>{E(h2)}</b></div>
<div class="card"><img src="{photos[0]}"></div>{poff}
<div class="name">{E(name)}</div>
<div class="prow"><span class="amt">{rupee(price) if price else 'BEST PRICE'}</span>{pmrp}</div>
<div class="chips"><div>💵 Cash on Delivery</div><div>🚚 Pan-India</div><div>💬 WhatsApp Order</div></div>
<div class="cta">🛒 Order now · www.kmscart.com</div>
</body></html>"""
Path("poster.html").write_text(poster_html, encoding="utf-8")

# ---------- music (synth, royalty free, varies per run) ----------
sr = 44100
t = np.arange(int(sr * DUR)) / sr
out = np.zeros_like(t)
rng = np.random.default_rng(run)


def env(n, a=0.005, d=0.3):
    x = np.arange(n) / sr
    return np.minimum(1, x / a) * np.exp(-x / d)


def add(sig, start):
    i = int(start * sr); j = min(len(out), i + len(sig))
    if i < len(out):
        out[i:j] += sig[: j - i]


beat = 0.5
for k in range(int(DUR / beat)):
    s = k * beat
    if s < 1.9:
        continue
    n = int(0.35 * sr); x = np.arange(n) / sr
    add(np.sin(2 * np.pi * (55 + 90 * np.exp(-x * 30)) * x) * env(n, 0.001, 0.12) * 0.9, s)
    if k % 2:
        add(rng.standard_normal(int(0.2 * sr)) * env(int(0.2 * sr), 0.001, 0.05) * 0.35, s)
    for hh in (0, 0.25):
        add(rng.standard_normal(int(0.05 * sr)) * env(int(0.05 * sr), 0.0005, 0.01) * 0.12, s + hh)
progs = [[[220, 277.2, 329.6], [174.6, 220, 261.6], [196, 246.9, 293.7], [164.8, 207.7, 246.9]],
         [[261.6, 329.6, 392], [220, 261.6, 329.6], [174.6, 220, 261.6], [196, 246.9, 293.7]],
         [[293.7, 349.2, 440], [233.1, 293.7, 349.2], [261.6, 329.6, 392], [220, 277.2, 329.6]]]
chords = progs[run % 3]
for bar in range(6):
    s = bar * 2.0; c = chords[bar % 4]; n = int(2 * sr); x = np.arange(n) / sr
    add(sum(np.sin(2 * np.pi * f * x) + 0.3 * np.sin(4 * np.pi * f * x) for f in c) * 0.06 * np.minimum(1, x / 0.3), s)
    if s >= 2:
        add(np.sign(np.sin(np.pi * c[0] * x)) * 0.05 * env(n, 0.01, 0.6), s)
n = int(1.9 * sr); x = np.arange(n) / sr
add(rng.standard_normal(n) * (x / 1.9) ** 2 * 0.25 * np.sin(2 * np.pi * (200 + 600 * x) * x), 0)
for s in (1.95, 6.9, 9.0):
    n = int(1.2 * sr); x = np.arange(n) / sr
    add((np.sin(2 * np.pi * 45 * x) + rng.standard_normal(n) * 0.3) * env(n, 0.001, 0.4) * 0.8, s)
out *= np.minimum(1, (DUR - t) / 0.8)
out /= np.max(np.abs(out)) * 1.1
pcm = (out * 32767).astype(np.int16)
w = wave.open("music.wav", "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
w.writeframes(np.stack([pcm, pcm], 1).tobytes()); w.close()


# ---------- render ----------
async def render():
    os.makedirs("frames", exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": 1080, "height": 1350})
        await pg.goto(Path("poster.html").resolve().as_uri()); await pg.wait_for_timeout(800)
        await pg.screenshot(path="poster.jpg", type="jpeg", quality=92)
        await pg.set_viewport_size({"width": 1080, "height": 1920})
        await pg.goto(Path("video.html").resolve().as_uri()); await pg.wait_for_timeout(800)
        await pg.evaluate("document.getAnimations().forEach(a=>a.pause())")
        for i in range(FPS * DUR):
            await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={i * 1000 / FPS})")
            await pg.screenshot(path=f"frames/{i:04d}.jpg", type="jpeg", quality=90)
        await b.close()


asyncio.run(render())
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", "frames/%04d.jpg", "-i", "music.wav",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", "ad_video.mp4"], check=True)
print("done:", title, "| price", price, "mrp", compare, "| photos", len(photos), "| theme", run % 3)
