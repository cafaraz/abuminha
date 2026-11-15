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
WATERMARK = "abuminha.com"


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
        out.append({
            "id": p.stem, "title": d.get("title", ""), "desc": d.get("desc", ""),
            "cat": d.get("category", "islam"), "sub": d.get("sub") or "",
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
            "id": p.stem, "title": d.get("title", ""), "desc": d.get("desc", ""),
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
        for i in range(n):
            page = doc[i]
            r = page.rect
            page.insert_text((r.width - 78, r.height - 10), WATERMARK, fontsize=7,
                             color=(0.45, 0.45, 0.45), fill_opacity=0.55)
            pix = page.get_pixmap(dpi=DPI)
            name = f"{i + 1:03d}.jpg"
            pix.save(folder / name, jpg_quality=82)
            pages.append({"src": f"fb/{p.stem}/{name}", "w": pix.width, "h": pix.height})
        if not pages:
            continue
        out.append({
            "id": p.stem, "title": d.get("title", ""), "desc": d.get("desc", ""),
            "pages": pages, "total": doc.page_count,
            "note": d.get("note") or "ബാക്കി പേജുകൾ ഉടൻ വരുന്നു, ഇൻശാ അല്ലാഹ്.",
        })
        print(f"ഫ്ലിപ്പ് ബുക്ക് {p.stem}: {len(pages)}/{doc.page_count} പേജുകൾ")
    return out


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
    lib = {
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
