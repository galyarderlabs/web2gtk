import os
import io
import shutil
import tempfile
import subprocess
from urllib.parse import urljoin, urlparse
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

ICON_BASE = os.path.expanduser("~/.local/share/icons/hicolor")
SIZES = [32, 128, 256]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.3 Safari/605.1.15"
)


def ensure_icon_dirs():
    for s in SIZES:
        os.makedirs(os.path.join(ICON_BASE, f"{s}x{s}", "apps"), exist_ok=True)


def process_and_save_image(img: Image.Image, icon_name: str) -> bool:
    """Save PIL Image into hicolor icon directories at 32, 128, 256 sizes."""
    ensure_icon_dirs()
    # Convert image to RGBA if not already
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    for size in SIZES:
        target_path = os.path.join(ICON_BASE, f"{size}x{size}", "apps", f"{icon_name}.png")
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(target_path, "PNG")
    return True


def rasterize_svg(svg_bytes: bytes, icon_name: str) -> bool:
    """Use rsvg-convert or cairosvg to render SVG to PNG icon sizes."""
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

    # Hash name to choose pleasant hue
    import hashlib
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:6], 16)
    r = 40 + (h % 160)
    g = 40 + ((h >> 8) % 160)
    b = 40 + ((h >> 16) % 160)

    for size in SIZES:
        img = Image.new("RGBA", (size, size), (r, g, b, 255))
        draw = ImageDraw.Draw(img)
        
        # Round corners
        corner_radius = int(size * 0.22)
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (size, size)], corner_radius, fill=255)
        img.putalpha(mask)

        # Draw letter
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


def fetch_web_icon(url: str, icon_name: str, app_name: str = "") -> bool:
    """Scrape and download best icon from website URL."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    candidate_urls: List[str] = []

    try:
        resp = session.get(url, timeout=6)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 1. apple-touch-icon (usually highest quality)
            for link in soup.find_all("link", rel=lambda r: r and "apple-touch-icon" in r.lower()):
                href = link.get("href")
                if href:
                    candidate_urls.append(urljoin(url, href))

            # 2. rel="icon" or shortcut icon
            for link in soup.find_all("link", rel=lambda r: r and ("icon" in r.lower() or "shortcut icon" in r.lower())):
                href = link.get("href")
                if href:
                    candidate_urls.append(urljoin(url, href))

            # 3. web manifest
            for link in soup.find_all("link", rel=lambda r: r and "manifest" in r.lower()):
                manifest_url = urljoin(url, link.get("href", ""))
                try:
                    m_resp = session.get(manifest_url, timeout=4)
                    if m_resp.status_code == 200:
                        m_data = m_resp.json()
                        for icon_info in m_data.get("icons", []):
                            src = icon_info.get("src")
                            if src:
                                candidate_urls.append(urljoin(manifest_url, src))
                except Exception:
                    pass
    except Exception:
        pass

    # 4. Fallback to domain root favicon.ico
    parsed = urlparse(url)
    candidate_urls.append(f"{parsed.scheme}://{parsed.netloc}/favicon.ico")

    # Try downloading candidates in order
    for c_url in candidate_urls:
        try:
            r = session.get(c_url, timeout=4)
            if r.status_code == 200 and len(r.content) > 50:
                content_type = r.headers.get("Content-Type", "").lower()
                
                if "svg" in content_type or c_url.lower().endswith(".svg"):
                    if rasterize_svg(r.content, icon_name):
                        return True

                try:
                    img = Image.open(io.BytesIO(r.content))
                    if process_and_save_image(img, icon_name):
                        return True
                except Exception:
                    continue
        except Exception:
            continue

    # Fallback to generated icon
    return generate_fallback_icon(app_name or icon_name, icon_name)
