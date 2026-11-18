"""abuminha.com സൈറ്റ് നിർമ്മിക്കുന്ന സ്ക്രിപ്റ്റ്.

content/ ഫോൾഡറിലെ ലേഖനങ്ങളും പുസ്തകങ്ങളും വായിച്ച്, പ്രസിദ്ധീകരിക്കാൻ
അനുവദിച്ചവ മാത്രം dist/ ഫോൾഡറിലേക്ക് എഴുതുന്നു. PDF പുസ്തകങ്ങളുടെ
അനുവദിച്ച പേജുകൾ മാത്രം ചിത്രങ്ങളാക്കുന്നു; PDF ഫയൽ സൈറ്റിൽ പോകില്ല.
"""
import datetime
import json
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown
import pymupdf
import yaml

ROOT = Path(__file__).parent
OUT = ROOT / "dist"
TODAY = datetime.datetime.now(ZoneInfo("Asia/Dubai")).date()
DPI = 150
# PDF പേജ് എത്ര വലുതായാലും ചിത്രം ഈ അളവിൽ കവിയില്ല (A4 @150dpi).
# വലിയ ചിത്രങ്ങളാണ് ഫ്ലിപ്പ് ബുക്ക് ഹാങ്ങ് ആകാൻ കാരണമായിരുന്നത്.
MAX_W, MAX_H = 1240, 1754
THUMB_W = 180
WATERMARK = "abuminha.com"
CATEGORIES = {"islam", "aadarsham", "current", "politics", "vachanam", "family", "kids"}


def as_date(v):
    if not v:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v).strip()[:10])


def released(d):
    """പ്രസിദ്ധീകരിക്കുക ഓൺ ആണെങ്കിലും, റിലീസ് തീയതി എത്തിയെങ്കിലും മാത്രം."""
    if not d.get("publish"):
        return False
    rd = as_date(d.get("release_date"))
    return rd is None or rd <= TODAY


def written(v):
    """എഴുതിയ തീയതി: 2015 / 2015-08 / 2015-08-12 — അറിയുന്നത്ര മാത്രം."""
    if v in (None, ""):
        return ""
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()[:10]
    parts = [p for p in str(v).strip().replace("/", "-").split("-") if p.strip().isdigit()]
    if not parts or len(parts[0]) != 4:
        return ""
    return "-".join([parts[0]] + [f"{int(x):02d}" for x in parts[1:3]])


def md(text):
    return markdown.markdown(text or "", extensions=["extra", "sane_lists", "nl2br"])


def read_frontmatter(path):
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        return yaml.safe_load(fm) or {}, body
    return {}, raw


def build_articles():
    out = []
    for p in sorted((ROOT / "content/articles").glob("*.md")):
        d, body = read_frontmatter(p)
        if not released(d):
            continue
        lang = d.get("lang") or "ml"
        if lang == "en":  # ഇംഗ്ലീഷ് മാത്രം: പ്രധാന ഉള്ളടക്കം ഇംഗ്ലീഷ് ഫീൽഡുകളിൽ നിന്ന്
            body = d.get("body_en") or body
        main = d.get("category") or "islam"
        cats = [main] + [c for c in (d.get("also") or []) if c in CATEGORIES and c != main]
        out.append({
            "id": p.stem, "lang": lang, "both": bool(d.get("both_sections")), "cats": list(dict.fromkeys(cats)),
            "title": d.get("title") or d.get("title_en") or "", "desc": d.get("desc") or "",
            "title_en": d.get("title_en") or "", "desc_en": d.get("desc_en") or "",
            "html_en": md(d.get("body_en", "")) if lang != "ml" else "",
            "written": written(d.get("written")), "context": str(d.get("context") or "").strip(),
            "author": str(d.get("author") or "").strip(), "author_info": str(d.get("author_info") or "").strip(),
            "cat": main, "sub": d.get("sub") or "",
            "date": str(as_date(d.get("release_date")) or as_date(d.get("date")) or ""),
            "html": md(body),
        })
    return out


def build_books():
    out = []
    for p in sorted((ROOT / "content/books").glob("*.yml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not d.get("publish"):
            continue
        chapters = d.get("chapters") or []
        live = [c for c in chapters if released(c)]
        if not live:
            continue
        upcoming = sorted(
            (as_date(c.get("release_date")) for c in chapters
             if c.get("publish") and as_date(c.get("release_date")) and not released(c)))
        out.append({
            "id": p.stem, "lang": d.get("lang") or "ml", "both": bool(d.get("both_sections")),
            "title": d.get("title", ""), "desc": d.get("desc", ""),
            "cover": d.get("cover") or "", "total": len(chapters),
            "next": str(upcoming[0]) if upcoming else "",
            "chapters": [{"t": c.get("title", ""), "html": md(c.get("body", ""))} for c in live],
        })
    return out


def build_flipbooks():
    out = []
    for p in sorted((ROOT / "content/flipbooks").glob("*.yml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not d.get("publish") or not d.get("pdf"):
            continue
        pdf = ROOT / str(d["pdf"]).lstrip("/")
        if not pdf.exists():
            print(f"!! PDF കണ്ടില്ല: {pdf}")
            continue
        doc = pymupdf.open(pdf)
        n = min(int(d.get("pages") or 0), doc.page_count)
        folder = OUT / "fb" / p.stem
        folder.mkdir(parents=True, exist_ok=True)
        pages = []
        thumb = ""
        for i in range(n):
            page = doc[i]
            r = page.rect
            k = r.width / 595  # വാട്ടർമാർക്ക് പേജ് വലുപ്പത്തിനനുസരിച്ച്
            page.insert_text((r.width - 78 * k, r.height - 10 * k), WATERMARK, fontsize=7 * k,
                             color=(0.45, 0.45, 0.45), fill_opacity=0.55)
            z = min(DPI / 72, MAX_W / r.width, MAX_H / r.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z))
            name = f"{i + 1:03d}.jpg"
            pix.save(folder / name, jpg_quality=80)
            pages.append({"src": f"fb/{p.stem}/{name}", "w": pix.width, "h": pix.height})
            if i == 0:  # കാർഡിലെ ചെറിയ ചിത്രം
                tz = THUMB_W / r.width
                page.get_pixmap(matrix=pymupdf.Matrix(tz, tz)).save(folder / "thumb.jpg", jpg_quality=78)
                thumb = f"fb/{p.stem}/thumb.jpg"
        if not pages:
            continue
        out.append({
            "id": p.stem, "lang": d.get("lang") or "ml", "both": bool(d.get("both_sections")),
            "title": d.get("title", ""), "desc": d.get("desc", ""),
            "pages": pages, "thumb": thumb, "total": doc.page_count,
            "note": d.get("note") or "ബാക്കി പേജുകൾ ഉടൻ വരുന്നു, ഇൻശാ അല്ലാഹ്.",
        })
        print(f"ഫ്ലിപ്പ് ബുക്ക് {p.stem}: {len(pages)}/{doc.page_count} പേജുകൾ")
    return out


def build_icons(logo):
    """ആപ്പ് ഐക്കണുകൾ: സൈറ്റ് ലോഗോയിൽ നിന്ന്."""
    from PIL import Image
    folder = OUT / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    src = ROOT / str(logo or "").lstrip("/")
    lg = Image.open(src).convert("RGBA") if logo and src.exists() else None
    for size, frac, name in [(192, .9, "icon-192.png"), (512, .9, "icon-512.png"),
                             (512, .68, "maskable-512.png"), (180, .86, "apple-touch-icon.png")]:
        im = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        if lg:
            s = int(size * frac)
            m = lg.resize((s, s), Image.LANCZOS)
            im.alpha_composite(m, ((size - s) // 2, (size - s) // 2))
        im.convert("RGB").save(folder / name)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "site", OUT)
    up = ROOT / "uploads"
    if up.exists():  # ചിത്രങ്ങൾ മാത്രം; PDF ഒരിക്കലും സൈറ്റിലേക്ക് പോകില്ല
        for f in up.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
                dst = OUT / "uploads" / f.relative_to(up)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
    sp = ROOT / "content/settings.yml"
    s = (yaml.safe_load(sp.read_text(encoding="utf-8")) or {}) if sp.exists() else {}
    s = {k: ("" if v is None else v) for k, v in s.items()}
    s["about"] = md(s.get("about", ""))
    s["about_en"] = md(s.get("about_en", ""))
    s["popular"] = [str(x) for x in (s.get("popular") or [])][:6]
    for k in ("logo", "logo_footer", "hero_image"):
        s[k] = str(s.get(k) or "").lstrip("/")
    build_icons(s.get("logo"))
    lib = {
        "settings": s,
        "articles": build_articles(),
        "books": build_books(),
        "flipbooks": build_flipbooks(),
        "built": str(TODAY),
    }
    (OUT / "data.js").write_text(
        "window.LIB=" + json.dumps(lib, ensure_ascii=False) + ";", encoding="utf-8")
    print(f"ലേഖനങ്ങൾ {len(lib['articles'])}, പുസ്തകങ്ങൾ {len(lib['books'])}, "
          f"ഫ്ലിപ്പ് ബുക്കുകൾ {len(lib['flipbooks'])}")


if __name__ == "__main__":
    main()
