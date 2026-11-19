#!/usr/bin/env python3
"""Build the static site: src/ -> docs/.  Run: python3 -I build.py"""
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "docs"
MEDIA = SRC / "media"
SITE_URL = "https://olegna27.github.io"
WIDTHS = (800, 1600)

NAV = [("projects", "index.html"), ("about", "about.html"), ("fix log", "fixlog.html"),
       ("resume", "Angelo_Chaca_Resume.pdf"), ("contact", "mailto:chaca@mit.edu")]
INDEX = [("drone dock", "dock.html"), ("heave simulator", "heave.html"), ("boat control and telemetry", "boat.html"),
         ("shadingbot", "shadingbot.html"), ("pompeii imaging", "earlier.html#pompeii"),
         ("asteroid orbit", "earlier.html#orbit"), ("rocket team and research", "earlier.html#rocket")]


def img_variants(rel):
    """Resize a raster into docs/media at each width; return (srcset, fallback, w, h)."""
    src = MEDIA / rel
    im = ImageOps.exif_transpose(Image.open(src))
    if im.mode in ("RGBA", "LA", "P"):
        rgba = im.convert("RGBA")
        im = Image.new("RGB", rgba.size, "white")
        im.paste(rgba, mask=rgba.split()[3])
    elif im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    w, h = im.size
    out = []
    for target in WIDTHS:
        tw = min(target, w)
        dst = OUT / "media" / Path(rel).with_name(f"{Path(rel).stem}-{tw}.jpg")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            im.resize((tw, round(h * tw / w)), Image.LANCZOS).save(dst, "JPEG", quality=82, optimize=True, progressive=True)
        out.append((dst.relative_to(OUT).as_posix(), tw))
        if tw == w:
            break
    srcset = ", ".join(f"{p} {tw}w" for p, tw in out)
    return srcset, out[0][0], w, h


def largest(rel):
    if rel.endswith(".svg"):
        return copy_media(rel)
    return img_variants(rel)[0].split(", ")[-1].split()[0]


def copy_media(rel):
    dst = OUT / "media" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MEDIA / rel, dst)
    return f"media/{rel}"


def svg_size(path):
    head = path.read_text(errors="ignore")[:2000]
    m = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', head)
    return (round(float(m.group(1))), round(float(m.group(2)))) if m else (1200, 800)


def img_tag(rel, alt, eager=False, sizes="(min-width: 62rem) 46rem, 100vw"):
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    alt = html.escape(alt, quote=True)
    if rel.endswith(".svg"):
        w, h = svg_size(MEDIA / rel)
        return f'<img src="{copy_media(rel)}" alt="{alt}" width="{w}" height="{h}" {load}>'
    srcset, fallback, w, h = img_variants(rel)
    return f'<img src="{fallback}" srcset="{srcset}" sizes="{sizes}" alt="{alt}" width="{w}" height="{h}" {load}>'


def video_tag(rel, poster, alt):
    w, h = video_size(MEDIA / rel)
    _, pfall, _, _ = img_variants(poster)
    return (
        f'<video src="{copy_media(rel)}" poster="{pfall}" width="{w}" height="{h}" muted loop playsinline controls data-auto '
        f'preload="metadata" aria-label="{html.escape(alt, quote=True)}"></video>'
    )


def video_size(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def expand(body):
    """Macros: {{img:path|alt}}  {{eager:path|alt}}  {{tile:path|alt}}  {{fig:path|alt|caption|classes}}  {{vid:path|poster|alt}}"""
    def fig(m):
        rel, alt, cap, *cls = [s.strip() for s in m.group(1).split("|")]
        frame = cls[0] if cls else ""
        wide = " wide" if "wide" in frame else ""
        frame = frame.replace("wide", "").strip()
        return (
            f'<figure class="{wide.strip()}"><div class="frame {frame}"><a href="{largest(rel)}">{img_tag(rel, alt)}</a></div>'
            f"<figcaption>{cap}</figcaption></figure>"
        )

    body = re.sub(r"\{\{fig:(.+?)\}\}", fig, body, flags=re.S)
    body = re.sub(r"\{\{img:(.+?)\|(.+?)\}\}", lambda m: img_tag(m.group(1).strip(), m.group(2).strip()), body)
    body = re.sub(r"\{\{eager:(.+?)\|(.+?)\}\}", lambda m: img_tag(m.group(1).strip(), m.group(2).strip(), eager=True, sizes="(min-width: 70rem) 65rem, 100vw"), body)
    body = re.sub(r"\{\{thumb:(.+?)\|(.+?)\}\}", lambda m: img_tag(m.group(1).strip(), m.group(2).strip(), eager=True, sizes="(min-width: 70rem) 17rem, (min-width: 56rem) 30vw, 45vw").replace(' fetchpriority="high"', ""), body)
    body = re.sub(r"\{\{vid:(.+?)\|(.+?)\|(.+?)\}\}", lambda m: video_tag(m.group(1).strip(), m.group(2).strip(), m.group(3).strip()), body)
    body = re.sub(r"\{\{file:(.+?)\}\}", lambda m: copy_media(m.group(1).strip()), body)
    return body


UNITS = r"(?:mm/s|cm/s|m/s²|m/s|mm|cm|m|N·m|kN|N|J|Hz|kg|kPa|V|A|in|rpm|µF|au|ms|s|ohms|hours|degrees|Ah|AWG|MB|x)"


def nbsp_units(body):
    out, in_pre = [], False
    for part in re.split(r"(<[^>]+>)", body):
        if part.startswith("<"):
            if part.startswith("<pre"):
                in_pre = True
            elif part.startswith("</pre"):
                in_pre = False
        elif not in_pre:
            part = re.sub(rf"(\d) ({UNITS})(?![\w/])", "\\1\u00a0\\2", part)
        out.append(part)
    return "".join(out)


def render(page):
    text = page.read_text()
    meta = json.loads(re.match(r"<!--(.*?)-->", text, re.S).group(1))
    body = nbsp_units(expand(text.split("-->", 1)[1]))
    name = page.name
    def links(items):
        return "".join(
            f'<a href="{href}"{" aria-current=\"page\"" if href == name else ""}>{label}</a>' for label, href in items
        )

    nav, index = links(NAV), links(INDEX)
    og_image = f"{SITE_URL}/{largest(meta['og_image'])}" if meta.get("og_image") else ""
    url = SITE_URL + ("/" if name == "index.html" else f"/{name}")
    head_extra = meta.get("head", "")
    base = (SRC / "base.html").read_text()
    out = (
        base.replace("{{title}}", html.escape(meta["title"]))
        .replace("{{description}}", html.escape(meta["description"], quote=True))
        .replace("{{og_title}}", html.escape(meta.get("og_title", meta["title"]), quote=True))
        .replace("{{og_image}}", og_image)
        .replace("{{url}}", url)
        .replace("{{nav}}", nav)
        .replace("{{index}}", index)
        .replace("{{head}}", head_extra)
        .replace("{{base}}", meta.get("base", ""))
        .replace("{{body}}", body)
    )
    (OUT / name).write_text(out)


def main():
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.html"):
        old.unlink()
    shutil.rmtree(OUT / "media", ignore_errors=True)
    shutil.copy2(SRC / "style.css", OUT / "style.css")
    shutil.copytree(ROOT / "assets" / "fonts", OUT / "fonts", dirs_exist_ok=True)
    shutil.copytree(ROOT / "assets" / "vendor", OUT / "vendor", dirs_exist_ok=True)
    (OUT / ".nojekyll").write_text("")
    shutil.copy2(SRC / "favicon.svg", OUT / "favicon.svg")
    shutil.copytree(SRC / "static", OUT, dirs_exist_ok=True)
    for page in sorted((SRC / "pages").glob("*.html")):
        render(page)
        print("built", page.name)
    unresolved = [p.name for p in OUT.glob("*.html") if "{{" in p.read_text()]
    assert not unresolved, f"unexpanded macro in {unresolved}"


if __name__ == "__main__":
    main()
