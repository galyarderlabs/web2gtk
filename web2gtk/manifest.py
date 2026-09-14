import os
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

CONFIG_BASE = os.path.expanduser("~/.config/web2gtk")
APPS_DIR = os.path.join(CONFIG_BASE, "apps")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)


def slugify(text: str) -> str:
    """Convert text into a safe filesystem/CLI slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-") or "web-app"


@dataclass
class AppManifest:
    name: str
    url: str
    slug: str = ""
    app_id: str = ""
    icon: str = ""
    user_agent: str = DEFAULT_USER_AGENT
    stealth: bool = False
    persistent_storage: bool = True
    system_tray: bool = True
    adblock: bool = True
    window: Dict[str, Any] = field(default_factory=lambda: {"width": 1080, "height": 800, "is_maximized": False})

    def __post_init__(self):
        if not self.slug:
            self.slug = slugify(self.name)
            if not self.slug.endswith("-gtk"):
                self.slug += "-gtk"

        if not self.app_id:
            safe_slug = self.slug.replace("-", "_")
            self.app_id = f"io.github.web2gtk.{safe_slug}"

        if not self.icon:
            self.icon = self.slug

        # Auto-migrate legacy Safari UA strings to modern Chrome Linux UA
        if not self.user_agent or "Version/18.0 Safari" in self.user_agent or "Version/60.5 Safari" in self.user_agent:
            self.user_agent = DEFAULT_USER_AGENT

    @property
    def data_dir(self) -> str:
        return os.path.expanduser(f"~/.local/share/{self.slug}")

    @property
    def cache_dir(self) -> str:
        return os.path.expanduser(f"~/.cache/{self.slug}")

    @property
    def config_dir(self) -> str:
        return os.path.expanduser(f"~/.config/{self.slug}")

    @property
    def manifest_path(self) -> str:
        return os.path.join(APPS_DIR, f"{self.slug}.json")

    def save(self):
        os.makedirs(APPS_DIR, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path_or_slug: str) -> "AppManifest":
        if os.path.exists(path_or_slug):
            path = path_or_slug
        else:
            slug = path_or_slug if path_or_slug.endswith("-gtk") else f"{path_or_slug}-gtk"
            path = os.path.join(APPS_DIR, f"{slug}.json")
            if not os.path.exists(path):
                # Try raw slug without -gtk
                path = os.path.join(APPS_DIR, f"{path_or_slug}.json")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Manifest not found for: {path_or_slug}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def list_all(cls) -> List["AppManifest"]:
        if not os.path.exists(APPS_DIR):
            return []
        apps = []
        for filename in sorted(os.listdir(APPS_DIR)):
            if filename.endswith(".json"):
                try:
                    apps.append(cls.load(os.path.join(APPS_DIR, filename)))
                except Exception:
                    pass
        return apps

    def delete(self):
        if os.path.exists(self.manifest_path):
            os.remove(self.manifest_path)
