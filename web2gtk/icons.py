import os
import io
import re
import shutil
import tempfile
import subprocess
from urllib.parse import urljoin, urlparse
from typing import Optional, List, Set
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

ICON_BASE = os.path.expanduser("~/.local/share/icons/hicolor")
SIZES = [32, 128, 256]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.3 Safari/605.1.15"
)

AUTH_DOMAINS = {
    "accounts.google.com",
    "login.microsoftonline.com",
    "appleid.apple.com",
    "auth0.com",
    "login.live.com",
}


def ensure_icon_dirs():
    for s in SIZES:
        os.makedirs(os.path.join(ICON_BASE, f"{s}x{s}", "apps"), exist_ok=True)


def process_and_save_image(img: Image.Image, icon_name: str) -> bool:
    """Save PIL Image into hicolor icon directories at 32, 128, 256 sizes."""
    ensure_icon_dirs()
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    for size in SIZES:
        target_path = os.path.join(ICON_BASE, f"{size}x{size}", "apps", f"{icon_name}.png")
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(target_path, "PNG")
    return True


def rasterize_svg(svg_bytes: bytes, icon_name: str) -> bool:
    """Use rsvg-convert to render SVG to PNG icon sizes."""
    ensure_icon_dirs()
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        f.write(svg_bytes)
        svg_path = f.name

    try:
        if shutil.which("rsvg-convert"):
            for size in SIZES:
                target_path = os.path.join(ICON_BASE, f"{size}x{size}", "apps", f"{icon_name}.png")
                subprocess.run(
                    ["rsvg-convert", "-w", str(size), "-h", str(size), "-f", "png", "-o", target_path, svg_path],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            return True
    except Exception:
        pass
    finally:
        if os.path.exists(svg_path):
            os.remove(svg_path)

    return False


def generate_fallback_icon(name: str, icon_name: str) -> bool:
    """Generate a clean minimalist colored square with the app's initial letter."""
    ensure_icon_dirs()
    letter = (name[0] if name else "W").upper()

    import hashlib
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:6], 16)
    r = 40 + (h % 160)
    g = 40 + ((h >> 8) % 160)
    b = 40 + ((h >> 16) % 160)

    for size in SIZES:
        img = Image.new("RGBA", (size, size), (r, g, b, 255))
        draw = ImageDraw.Draw(img)

        corner_radius = int(size * 0.22)
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (size, size)], corner_radius, fill=255)
        img.putalpha(mask)

        font_size = int(size * 0.55)
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), letter, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (size - text_w) / 2 - bbox[0]
        y = (size - text_h) / 2 - bbox[1]

        draw.text((x, y), letter, fill=(255, 255, 255, 255), font=font)

        target_path = os.path.join(ICON_BASE, f"{size}x{size}", "apps", f"{icon_name}.png")
        img.save(target_path, "PNG")

    return True


def install_local_icon(file_path: str, icon_name: str) -> bool:
    """Install an icon from a local file path (PNG, JPG, ICO, SVG, etc.)."""
    if not os.path.exists(file_path):
        return False

    if file_path.lower().endswith(".svg"):
        with open(file_path, "rb") as f:
            if rasterize_svg(f.read(), icon_name):
                return True

    try:
        img = Image.open(file_path)
        return process_and_save_image(img, icon_name)
    except Exception as e:
        print(f"Gagal memproses file icon lokal: {e}")
        return False


def get_candidate_pages(target_url: str) -> List[str]:
    """Generate smart candidate landing page URLs to avoid auth redirect traps."""
    parsed = urlparse(target_url)
    domain = parsed.netloc.lower()
    pages = [target_url]

    # Specific common Google services mapping
    if domain.endswith(".google.com"):
        sub = domain.replace(".google.com", "")
        pages.append(f"https://{sub}.google/")
        pages.append(f"https://{domain}/about")
        if sub.endswith("lm"):
            # e.g. notebooklm -> notebook.google/
            base_sub = sub[:-2]
            pages.append(f"https://{base_sub}.google/")
        else:
            pages.append(f"https://{sub}lm.google/")

    # Subdomain landing pages
    parts = domain.split(".")
    if len(parts) > 2:
        root_domain = ".".join(parts[-2:])
        pages.append(f"https://{root_domain}/")

    return pages


def fetch_web_icon(url: str, icon_name: str, app_name: str = "") -> bool:
    """
    Multi-tier high-fidelity icon discovery:
    1. Scraping HTML link tags & PWA manifests from smart landing pages.
    2. Vector SVGs preferred via rsvg-convert.
    3. Multi-source CDN fallback (Icon Horse, Google S2 256, DuckDuckGo, SimpleIcons).
    4. Quality sorting by resolution.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    svg_candidates: List[str] = []
    high_res_candidates: List[str] = []
    normal_candidates: List[str] = []
    seen_urls: Set[str] = set()

    def add_candidate(c_url: str):
        if c_url and c_url not in seen_urls:
            seen_urls.add(c_url)
            c_lower = c_url.lower()
            if "svg" in c_lower:
                svg_candidates.append(c_url)
            elif any(k in c_lower for k in ("apple-touch-icon", "pwa", "512", "256", "192")):
                high_res_candidates.append(c_url)
            else:
                normal_candidates.append(c_url)

    # 1. Scrape candidate landing pages
    for page_url in get_candidate_pages(url):
        try:
            resp = session.get(page_url, timeout=5)
            # Skip if redirected to generic login portal
            if urlparse(resp.url).netloc in AUTH_DOMAINS:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # A. <link> tags
            for link in soup.find_all("link"):
                rel = [r.lower() for r in link.get("rel", [])]
                href = link.get("href")
                if not href:
                    continue

                full_href = urljoin(resp.url, href)
                if any("apple-touch-icon" in r for r in rel):
                    high_res_candidates.append(full_href)
                    seen_urls.add(full_href)
                elif any("icon" in r for r in rel):
                    add_candidate(full_href)

            # B. PWA Web Manifest icons
            for link in soup.find_all("link", rel=lambda r: r and "manifest" in r.lower()):
                manifest_url = urljoin(resp.url, link.get("href", ""))
                try:
                    m_resp = session.get(manifest_url, timeout=3)
                    if m_resp.status_code == 200:
                        m_data = m_resp.json()
                        for icon_info in m_data.get("icons", []):
                            src = icon_info.get("src")
                            if src:
                                add_candidate(urljoin(manifest_url, src))
                except Exception:
                    pass
        except Exception:
            continue

    # 2. Add high-res Favicon CDNs as fallback candidates
    clean_domain = domain
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]

    # Icon Horse (usually serves high-res PNG)
    add_candidate(f"https://icon.horse/icon/{clean_domain}")
    # Google S2 256px
    add_candidate(f"https://www.google.com/s2/favicons?domain={clean_domain}&sz=256")
    # DuckDuckGo Favicon
    add_candidate(f"https://icons.duckduckgo.com/ip3/{clean_domain}.ico")

    # Brand SimpleIcons CDN
    if app_name:
        clean_name = re.sub(r"[^a-zA-Z0-9]", "", app_name).lower()
        if clean_name:
            add_candidate(f"https://cdn.simpleicons.org/{clean_name}")

    # Standard /favicon.ico
    add_candidate(f"{parsed.scheme}://{domain}/favicon.ico")

    # 3. Process candidate downloads in priority order: SVG -> High-res -> Normal
    all_ordered = svg_candidates + high_res_candidates + normal_candidates

    best_image: Optional[Image.Image] = None
    best_size = 0

    for c_url in all_ordered:
        try:
            r = session.get(c_url, timeout=4)
            if r.status_code != 200 or len(r.content) < 50:
                continue

            content_type = r.headers.get("Content-Type", "").lower()

            # If SVG, rasterize directly
            if "svg" in content_type or c_url.lower().endswith(".svg") or b"<svg" in r.content[:200]:
                if rasterize_svg(r.content, icon_name):
                    return True

            # If raster image
            try:
                img = Image.open(io.BytesIO(r.content))
                width, height = img.size
                current_size = width * height

                # If >= 128x128, it's high quality: save and finish
                if width >= 128 and height >= 128:
                    if process_and_save_image(img, icon_name):
                        return True

                if current_size > best_size:
                    best_image = img
                    best_size = current_size
            except Exception:
                continue
        except Exception:
            continue

    if best_image is not None:
        if process_and_save_image(best_image, icon_name):
            return True

    # Final Fallback to generated icon
    return generate_fallback_icon(app_name or icon_name, icon_name)
