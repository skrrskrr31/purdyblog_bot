"""
PURDYBLOG BOT - Yeni Sürüm
Gerekli dosyalar:
  haber.txt  → haber metni (sen yazarsın)
  foto1.jpg  → 1. fotoğraf (zorunlu)
  foto2.jpg  → 2. fotoğraf (opsiyonel, varsa yan yana gösterilir)
  logo.jpg   → kanal logosu
"""

import os, sys, random, base64, subprocess, json
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import io as _io
from PIL import Image, ImageDraw, ImageFont
from groq import Groq
from moviepy.editor import ImageClip, AudioFileClip

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except: pass

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

GROQ_API_KEY        = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")
SECRET_PATH  = os.path.join(script_dir, "secret.json")
TOKEN_PATH   = os.path.join(script_dir, "token.json")

# GitHub Actions: env var içeriklerini dosyaya yaz
_secret_env = os.environ.get("SECRET_JSON")
if _secret_env and not os.path.exists(SECRET_PATH):
    with open(SECRET_PATH, "w") as _f:
        _f.write(_secret_env)

_token_env = os.environ.get("TOKEN_JSON")
if _token_env and not os.path.exists(TOKEN_PATH):
    with open(TOKEN_PATH, "w") as _f:
        _f.write(_token_env)
OUTPUT_VIDEO = os.path.join(script_dir, "purdyblog_shorts.mp4")


# ─────────────────────────────────────────────────────────────
# TELEGRAM BİLDİRİM
# ─────────────────────────────────────────────────────────────
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    import urllib.request, urllib.parse
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=data
        )
        urllib.request.urlopen(req, timeout=10)
        print("[Telegram] Mesaj gonderildi.")
    except Exception as e:
        print(f"[Telegram] Hata: {e}")

W, H       = 1080, 1920
PAD        = 44
CHANNEL_NAME   = "purdyblog"
CHANNEL_HANDLE = "@purdyblog"



# ─────────────────────────────────────────────────────────────
# YARDIMCILAR
# ─────────────────────────────────────────────────────────────
def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: continue
    return ImageFont.load_default(size=size)


def draw_verified(draw, x, y, size=30):
    """Mavi onay rozeti."""
    draw.ellipse([x, y, x+size, y+size], fill=(29, 155, 240))
    # Beyaz tik çiz
    m = size * 0.18
    p1 = (x + size*0.22, y + size*0.52)
    p2 = (x + size*0.44, y + size*0.72)
    p3 = (x + size*0.78, y + size*0.28)
    draw.line([p1, p2], fill="white", width=max(2, int(size*0.13)))
    draw.line([p2, p3], fill="white", width=max(2, int(size*0.13)))


def paste_circular_logo(img, logo_path, x, y, size):
    """Yuvarlak logo yapıştır."""
    try:
        logo = Image.open(logo_path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        logo.putalpha(mask)
        img.paste(logo, (x, y), logo)
    except:
        # Logo yoksa gri daire
        ImageDraw.Draw(img).ellipse([x, y, x+size, y+size], fill=(60, 60, 60))
        f = load_font(size//2, bold=True)
        ImageDraw.Draw(img).text((x + size//4, y + size//8), "P", font=f, fill="white")


def wrap_text(draw, text, font, max_width):
    """Metni satırlara böl."""
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            w = draw.textbbox((0, 0), test, font=font)[2]
            if w > max_width and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
    return lines


# ─────────────────────────────────────────────────────────────
# KART GÖRSELİ OLUŞTUR
# ─────────────────────────────────────────────────────────────
def create_card(haber_metni, foto_paths):
    img  = Image.new("RGB", (W, H), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    f_name   = load_font(46, bold=True)
    f_handle = load_font(34, bold=False)
    f_text   = load_font(43, bold=False)

    logo_size  = 88
    line_h     = 62
    text_maxw  = W - PAD * 2
    photo_h    = 520
    gap_2foto  = 14

    # ── Toplam içerik yüksekliğini hesapla (dikey ortalama için) ──
    header_h = logo_size + 28  # logo + alt boşluk

    lines = wrap_text(draw, haber_metni, f_text, text_maxw)
    text_h = 0
    for line in lines:
        text_h += line_h // 2 if line == "" else line_h
    text_h += 20  # yazı-fotoğraf arası

    foto_h_actual = photo_h if foto_paths else 0

    total_h  = header_h + text_h + foto_h_actual
    start_y  = (H - total_h) // 2  # dikey merkez
    start_y  = max(PAD, start_y)   # üstten en az PAD boşluk

    # ── Header ───────────────────────────────────────────────
    lx, ly = PAD, start_y
    paste_circular_logo(img, os.path.join(script_dir, "logo.jpg"), lx, ly, logo_size)

    tx      = lx + logo_size + 20
    ty_name = ly + 10
    draw.text((tx, ty_name), CHANNEL_NAME, font=f_name, fill="white")
    nw = draw.textbbox((0, 0), CHANNEL_NAME, font=f_name)[2]
    draw_verified(draw, tx + nw + 10, ty_name + 6, size=32)

    ty_handle = ty_name + draw.textbbox((0, 0), CHANNEL_NAME, font=f_name)[3] + 6
    draw.text((tx, ty_handle), CHANNEL_HANDLE, font=f_handle, fill=(140, 140, 140))

    # ── Haber Metni ──────────────────────────────────────────
    text_y = start_y + header_h
    for line in lines:
        if line == "":
            text_y += line_h // 2
            continue
        draw.text((PAD, text_y), line, font=f_text, fill="white")
        text_y += line_h

    # ── Fotoğraflar ──────────────────────────────────────────
    photos_top = text_y + 20

    if len(foto_paths) == 1:
        try:
            foto = Image.open(foto_paths[0]).convert("RGB")
            fw, fh = foto.size
            tw, th = W - PAD * 2, photo_h
            ratio  = min(tw / fw, th / fh)
            nw2, nh2 = int(fw * ratio), int(fh * ratio)
            foto = foto.resize((nw2, nh2), Image.Resampling.LANCZOS)
            img.paste(foto, (PAD + (tw - nw2) // 2, photos_top + (th - nh2) // 2))
        except Exception as e:
            print(f"[WARN] foto1 yuklenemedi: {e}")

    elif len(foto_paths) >= 2:
        each_w = (W - PAD * 2 - gap_2foto) // 2
        each_h = photo_h
        for idx in range(2):
            try:
                foto = Image.open(foto_paths[idx]).convert("RGB")
                fw, fh = foto.size
                ratio  = min(each_w / fw, each_h / fh)
                nw2, nh2 = int(fw * ratio), int(fh * ratio)
                foto_r = foto.resize((nw2, nh2), Image.Resampling.LANCZOS)
                slot   = Image.new("RGB", (each_w, each_h), (0, 0, 0))
                slot.paste(foto_r, ((each_w - nw2) // 2, (each_h - nh2) // 2))
                img.paste(slot, (PAD + idx * (each_w + gap_2foto), photos_top))
            except Exception as e:
                print(f"[WARN] foto{idx+1} yuklenemedi: {e}")

    return img


# ─────────────────────────────────────────────────────────────
# OTOMATİK HABER ÇEKİCİ
# ─────────────────────────────────────────────────────────────
KULLANILAN_PATH = os.path.join(script_dir, "kullanilan_haberler.json")


def haber_cek():
    """haberler.com/magazin'den en son kullanılmamış haberi çek."""
    import requests
    from bs4 import BeautifulSoup

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    print("Haberler.com'dan haber cekiliyor...")
    try:
        r = requests.get('https://www.haberler.com/magazin/', headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"[ERROR] Liste sayfasi cekilemedi: {e}")
        return None, None

    # Haber linklerini topla
    haberler = []
    goruldu = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'haberi' not in href or '/magazin/' not in href:
            continue
        url = ('https://www.haberler.com' + href) if href.startswith('/') else href
        if url in goruldu:
            continue
        goruldu.add(url)
        baslik = a.get_text(strip=True)
        if len(baslik) > 15:
            haberler.append((baslik, url))

    if not haberler:
        print("[WARN] Haber bulunamadi.")
        return None, None

    # Daha önce kullanılanları filtrele
    gecmis = []
    if os.path.exists(KULLANILAN_PATH):
        try:
            with open(KULLANILAN_PATH, 'r', encoding='utf-8') as f:
                gecmis = json.load(f)
        except: pass

    # gecmis artık [{"url":..., "baslik":...}] formatında, eski format [str] de desteklenir
    gecmis_urls = set()
    gecmis_basliklar = []
    for item in gecmis:
        if isinstance(item, dict):
            gecmis_urls.add(item.get("url", ""))
            gecmis_basliklar.append(item.get("baslik", "").lower())
        else:
            gecmis_urls.add(item)

    def baslik_benzer(b1, b2, esik=0.5):
        """İki başlık arasındaki kelime örtüşmesini kontrol et."""
        k1 = set(w for w in b1.lower().split() if len(w) > 3)
        k2 = set(w for w in b2.lower().split() if len(w) > 3)
        if not k1 or not k2:
            return False
        oran = len(k1 & k2) / min(len(k1), len(k2))
        return oran >= esik

    def url_veya_baslik_kullanildi(baslik, url):
        if url in gecmis_urls:
            return True
        return any(baslik_benzer(baslik, gb) for gb in gecmis_basliklar)

    yeni = [(b, u) for b, u in haberler if not url_veya_baslik_kullanildi(b, u)]
    if not yeni:
        print("[INFO] Tum haberler kullanildi, sifirlaniyor.")
        yeni = haberler

    secilen_baslik, secilen_url = yeni[0]
    print(f"[OK] Haber secildi: {secilen_baslik[:60]}")

    # Haber sayfasına gir
    try:
        r2 = requests.get(secilen_url, headers=headers, timeout=15)
        soup2 = BeautifulSoup(r2.text, 'html.parser')
    except Exception as e:
        print(f"[ERROR] Haber sayfasi cekilemedi: {e}")
        return None, None

    # Metin çek
    metin = ""
    for selector in ['div.haberDetay', 'div.haber-detay', 'div.news-content', 'article']:
        el = soup2.select_one(selector)
        if el:
            for tag in el(['script', 'style', 'nav', 'aside', 'figure']):
                tag.decompose()
            satirlar = [s.strip() for s in el.get_text('\n').split('\n') if len(s.strip()) > 35]
            metin = '\n'.join(satirlar)
            break
    if not metin:
        paragraflar = [p.get_text(strip=True) for p in soup2.find_all('p') if len(p.get_text(strip=True)) > 40]
        metin = '\n'.join(paragraflar)
    if not metin:
        metin = secilen_baslik

    # Fotoğraf çek (og:image)
    foto_path = None
    og = soup2.find('meta', property='og:image')
    if og and og.get('content'):
        try:
            r3 = requests.get(og['content'], headers=headers, timeout=15)
            foto_path = os.path.join(script_dir, 'orijinal_gonderi.jpg')
            with open(foto_path, 'wb') as f:
                f.write(r3.content)
            # Varsa ikinci fotoyu sil
            for ext in ['.jpg', '.jpeg', '.png']:
                p2 = os.path.join(script_dir, f'orijinal_gonderi2{ext}')
                if os.path.exists(p2):
                    os.remove(p2)
            print(f"[OK] Foto indirildi.")
        except Exception as e:
            print(f"[WARN] Foto indirilemedi: {e}")

    # Geçmişe kaydet (yeni format: {"url":..., "baslik":...})
    yeni_kayit = {"url": secilen_url, "baslik": secilen_baslik}
    # Eski format uyumu: string olanları objeye çevir
    gecmis_normalize = []
    for item in gecmis:
        if isinstance(item, str):
            gecmis_normalize.append({"url": item, "baslik": ""})
        else:
            gecmis_normalize.append(item)
    gecmis_normalize.append(yeni_kayit)
    with open(KULLANILAN_PATH, 'w', encoding='utf-8') as f:
        json.dump(gecmis_normalize[-30:], f, ensure_ascii=False)

    return metin, foto_path


# ─────────────────────────────────────────────────────────────
# MÜZİK SEÇİMİ
# ─────────────────────────────────────────────────────────────
# Şarkıcı olmayan kişiler için sözsüz arka plan müziği arama terimleri
INSTRUMENTAL_SEARCHES = [
    "lofi chill background music no lyrics",
    "soft piano background music relaxing",
    "ambient background music calm instrumental",
    "chill lofi beats study music",
    "gentle background music no vocals",
    "cinematic background music soft",
    "lo fi hip hop relaxing instrumental",
    "peaceful background music no words",
    "smooth jazz background music light",
    "aesthetic background music instrumental chill",
]


def pick_muzik_local(haber_metni):
    """Groq ile haberın tonuna göre eglenceli/huzunlu klasöründen müzik seçer.
    Döndürür: (muzik_dosyasi, volume: float)"""
    print("Muzik seciliyor (yerel)...")

    muzikler_dir = os.path.join(script_dir, "muzikler")
    eglen_dir = os.path.join(muzikler_dir, "eglenceli")
    huzun_dir = os.path.join(muzikler_dir, "huzunlu")

    eglen_files = [os.path.join(eglen_dir, f) for f in os.listdir(eglen_dir) if f.endswith(".mp3")] if os.path.isdir(eglen_dir) else []
    huzun_files = [os.path.join(huzun_dir, f) for f in os.listdir(huzun_dir) if f.endswith(".mp3")] if os.path.isdir(huzun_dir) else []
    tum_files   = eglen_files + huzun_files

    if not tum_files:
        print("[WARN] Yerel muzik dosyasi bulunamadi.")
        return None, 0.15

    # Groq ile ton tespiti
    ton = "eglenceli"
    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content":
                f'Su Turk magazin haberinin genel tonu nedir?\n\n'
                f'HABER: "{haber_metni[:300]}"\n\n'
                f'Sadece tek kelime yaz: EGLENCELI veya HUZUNLU'}]
        )
        yanit = resp.choices[0].message.content.strip().upper()
        if "HUZUNLU" in yanit:
            ton = "huzunlu"
        print(f"[OK] Haber tonu: {ton}")
    except Exception as e:
        print(f"[WARN] Groq ton hatasi: {e}")

    # Tona uygun klasörden seç, yoksa tüm dosyalardan
    if ton == "huzunlu" and huzun_files:
        secilen = random.choice(huzun_files)
    elif eglen_files:
        secilen = random.choice(eglen_files)
    else:
        secilen = random.choice(tum_files)

    print(f"[OK] Muzik: {os.path.basename(secilen)}")
    return secilen, 0.20


# ─────────────────────────────────────────────────────────────
# GROQ METİN ÖZETİ
# ─────────────────────────────────────────────────────────────
def metin_ozet(haber_metni):
    """Groq ile uzun haberi 2-3 kısa cümleye indir (video kartına sığacak şekilde)."""
    print("Metin ozetlen iyor...")
    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content":
                f'Şu haberi Türkçe olarak maksimum 2-3 kısa cümleyle özetle. '
                f'Toplam 200 karakteri geçme. Sansasyonel ve merak uyandırıcı yaz. '
                f'Sadece özet metni yaz, başka hiçbir şey ekleme:\n\n{haber_metni[:1000]}'}]
        )
        ozet = resp.choices[0].message.content.strip()
        print(f"[OK] Ozet: {ozet[:80]}...")
        return ozet
    except Exception as e:
        print(f"[WARN] Ozet hatasi: {e}")
        # Fallback: ilk 200 karakter
        return haber_metni[:200].rsplit(' ', 1)[0] + "..."


# ─────────────────────────────────────────────────────────────
# GROQ BAŞLIK
# ─────────────────────────────────────────────────────────────
def generate_title(haber_metni):
    print("Baslik uretiliyor...")
    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content":
                f'Sen Türkiye\'nin en iyi magazin sayfası editörüsün. '
                f'Şu haberi oku: "{haber_metni[:400]}"\n\n'
                f'İnsanların kaydırırken durmasını sağlayacak, merak uyandırıcı bir YouTube Shorts başlığı yaz. '
                f'Max 60 karakter. Olayın sırrını tamamen verme. Sonda #shorts yaz. '
                f'SADECE BAŞLIĞI YAZ:'}]
        )
        title = resp.choices[0].message.content.strip().replace('"', '').strip()
        if title:
            print(f"[OK] Baslik: {title}")
            return title
    except Exception as e:
        print(f"[WARN] Groq hatasi: {e}")

    hooks = [
        "İnanılmaz! Herkes bunu konuşuyor 😱 #shorts",
        "Şok eden gelişme! Ne olduğunu görün #shorts",
        "Bunu kimse beklemiyordu! 😮 #shorts",
        "Gündem olan olay! Detaylar burada #shorts",
    ]
    return random.choice(hooks)


# ─────────────────────────────────────────────────────────────
# VİDEO OLUŞTUR
# ─────────────────────────────────────────────────────────────
def create_video(img, secilen_muzik=None, volume=0.20):
    print("Video olusturuluyor...")
    temp = "_temp_card.jpg"
    img.save(temp, quality=95)

    clip = ImageClip(temp, duration=7)

    if secilen_muzik and os.path.exists(secilen_muzik):
        try:
            audio = AudioFileClip(secilen_muzik)
            start = random.randint(0, max(0, int(audio.duration) - 10))
            audio = audio.subclip(start, min(start + 7, audio.duration))
            audio = audio.volumex(volume)
            clip = clip.set_audio(audio)
            print(f"[OK] Muzik eklendi (volume={volume})")
        except Exception as e:
            print(f"[WARN] Muzik eklenemedi: {e}")

    clip.write_videofile(OUTPUT_VIDEO, fps=24, codec="libx264", logger=None)

    try: os.remove(temp)
    except: pass

    print(f"[OK] Video hazir: {OUTPUT_VIDEO}")


# ─────────────────────────────────────────────────────────────
# YOUTUBE UPLOAD
# ─────────────────────────────────────────────────────────────
def upload_to_youtube(title, description):
    print("\nYouTube'a yukleniyor...")

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    if not os.path.exists(SECRET_PATH):
        print(f"[ERROR] {SECRET_PATH} bulunamadi. Yukleme atlaniyor.")
        return

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    creds  = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow  = InstalledAppFlow.from_client_secrets_file(SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())

    yt   = build('youtube', 'v3', credentials=creds)
    body = {
        'snippet': {
            'title':       title[:100],
            'description': description,
            'tags':        ['shorts', 'magazin', 'haber', 'gundem', 'turkiye'],
            'categoryId':  '24'  # Entertainment
        },
        'status': {
            'privacyStatus':          'public',
            'selfDeclaredMadeForKids': False
        }
    }

    try:
        media = MediaFileUpload(OUTPUT_VIDEO, mimetype='video/mp4', resumable=True)
        req   = yt.videos().insert(part='snippet,status', body=body, media_body=media)
        response = None
        while response is None:
            status, response = req.next_chunk()
            if status:
                print(f"  %{int(status.progress() * 100)}")
        video_id = response['id']
        print(f"\n[OK] Yayinlandi! https://youtube.com/shorts/{video_id}")
        return video_id
    except Exception as e:
        print(f"[ERROR] YouTube yukleme hatasi: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# ÇALIŞMA LOGU
# ─────────────────────────────────────────────────────────────
def save_run_log(status, video_id=None, title=None, error=None):
    from datetime import datetime
    log_path = os.path.join(script_dir, "run_log.json")
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {"bot": "purdyblog", "runs": []}
    entry = {"ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "status": status}
    if video_id: entry["video_id"] = video_id
    if title:    entry["title"]    = title[:80]
    if error:    entry["error"]    = str(error)[:200]
    data["runs"].append(entry)
    data["runs"] = data["runs"][-20:]
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────
# ANA AKIŞ
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    TEST_MODE = "--test" in sys.argv
    print("=== PURDYBLOG BOT" + (" [TEST MODU]" if TEST_MODE else "") + " ===\n")

    # Önce haber.txt'e bak - doluysa onu kullan, boşsa otomatik çek
    haber_path = os.path.join(script_dir, "haber.txt")
    haber_metni = ""
    if os.path.exists(haber_path):
        with open(haber_path, 'r', encoding='utf-8') as f:
            haber_metni = f.read().strip()

    if haber_metni:
        print(f"haber.txt'den okundu ({len(haber_metni)} karakter)")
        # Fotoğrafları bul
        foto_paths = []
        for isim in ["orijinal_gonderi", "orijinal_gonderi2"]:
            for ext in ['.jpg', '.jpeg', '.png']:
                p = os.path.join(script_dir, f"{isim}{ext}")
                if os.path.exists(p):
                    foto_paths.append(p)
                    break
    else:
        print("haber.txt bos - otomatik haber cekiliyor...\n")
        haber_metni, foto_auto = haber_cek()
        if not haber_metni:
            print("[ERROR] Haber cekilemedi, haber.txt de bos. Cikiyor.")
            sys.exit(1)
        foto_paths = [foto_auto] if foto_auto else []

    print(f"{len(foto_paths)} fotograf bulundu.\n")

    # Metni kısalt (video kartına sığacak şekilde) sonra kartı oluştur
    haber_kisa = metin_ozet(haber_metni)
    img = create_card(haber_kisa, foto_paths)

    # Başlık + müzik seçimi
    title                  = generate_title(haber_metni)
    secilen_muzik, volume  = pick_muzik_local(haber_metni)
    description            = haber_metni[:300] + "\n\n#shorts #magazin #haber #gundem #turkiye #kesfet"

    # Video
    create_video(img, secilen_muzik, volume=volume)

    # YouTube
    if TEST_MODE:
        print("\n[TEST] YouTube yuklemesi atlandi.")
        print(f"[TEST] Video: {OUTPUT_VIDEO}")
    else:
        video_id = upload_to_youtube(title, description)
        if video_id:
            save_run_log("ok", video_id=video_id, title=title)
            send_telegram(
                f"✅ <b>purdyblog</b> video yayınlandı!\n"
                f"🎬 {title}\n"
                f"🔗 https://youtube.com/shorts/{video_id}"
            )
        else:
            save_run_log("error", error="YouTube upload failed")
            send_telegram("❌ <b>purdyblog</b> YouTube yüklemesi başarısız!")

    print("\n=== Tamamlandi! ===")
