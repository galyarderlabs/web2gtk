import os
import json
import re
from urllib.parse import urlparse
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')

from gi.repository import Gtk, Adw, WebKit, GLib, Gdk, Gio

try:
    from web2gtk.engine.adblock import setup_adblock
except ImportError:
    from adblock import setup_adblock

STEALTH_SCRIPT = """
try {
    Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
        configurable: true
    });
} catch(e) {}
"""

AUTH_DOMAINS = (
    "accounts.google.com",
    "appleid.apple.com",
    "login.microsoftonline.com",
    "login.live.com",
    "github.com",
    "auth0.com",
    "clerk.com",
    "okta.com",
)


def is_auth_url(url_str):
    if not url_str:
        return False
    try:
        from urllib.parse import urlparse
        p = urlparse(url_str)
        host = p.netloc.lower()
        if any(ad in host for ad in AUTH_DOMAINS):
            return True
        path = p.path.lower()
        if any(kw in path for kw in ("/auth/", "/login", "/signin", "/oauth", "/sso")):
            return True
    except Exception:
        pass
    return False


def is_same_app_domain(url_str, app_url):
    if not url_str or not app_url:
        return False
    try:
        from urllib.parse import urlparse
        target_host = urlparse(url_str).netloc.lower()
        app_host = urlparse(app_url).netloc.lower()
        if target_host == app_host or target_host.endswith("." + app_host):
            return True
        if "notebook" in app_host and "notebook" in target_host and target_host.endswith(".google.com"):
            return True
        parts_target = target_host.split(".")
        parts_app = app_host.split(".")
        if len(parts_target) >= 2 and len(parts_app) >= 2:
            root_target = ".".join(parts_target[-2:])
            root_app = ".".join(parts_app[-2:])
            if root_target == root_app and root_target not in ("google.com", "github.com", "microsoft.com", "apple.com"):
                return True
    except Exception:
        pass
    return False


LLM_CHAT_DOMAINS = (
    "chatgpt.com",
    "claude.ai",
    "gemini.google.com",
    "chat.mistral.ai",
)


def is_llm_chat_app(url_str):
    if not url_str:
        return False
    try:
        from urllib.parse import urlparse
        host = urlparse(url_str).netloc.lower()
        return any(d in host for d in LLM_CHAT_DOMAINS)
    except Exception:
        return False


def is_tiktok_app(url_str):
    if not url_str:
        return False
    try:
        from urllib.parse import urlparse
        host = urlparse(url_str).netloc.lower()
        return "tiktok.com" in host
    except Exception:
        return False


# TikTok feed navigation & performance bridge
TIKTOK_OPTIMIZATION_SCRIPT = """
(function() {
    let accumulatedDelta = 0;
    let lastNavTime = 0;
    const COOLDOWN_MS = 360;
    const THRESHOLD = 25;

    function getNavButtons() {
        const nextBtn = document.querySelector(
            'button[data-e2e="feed-navigation-next"], button[data-key-interaction="feed_nav_next"], [data-e2e="arrow-down"], [data-e2e="feed-arrow-down"]'
        );
        const prevBtn = document.querySelector(
            'button[data-e2e="feed-navigation-prev"], button[data-key-interaction="feed_nav_prev"], [data-e2e="arrow-up"], [data-e2e="feed-arrow-up"]'
        );
        return { nextBtn, prevBtn };
    }

    function navigate(dir) {
        const now = Date.now();
        if (now - lastNavTime < COOLDOWN_MS) return false;
        const { nextBtn, prevBtn } = getNavButtons();

        if (dir === 'next' && nextBtn && typeof nextBtn.click === 'function') {
            nextBtn.click();
            lastNavTime = now;
            return true;
        } else if (dir === 'prev' && prevBtn && typeof prevBtn.click === 'function') {
            prevBtn.click();
            lastNavTime = now;
            return true;
        }
        return false;
    }

    // Wheel event bridge for smooth, responsive 1-video scrolling
    window.addEventListener('wheel', (e) => {
        if (e.target && e.target.closest('[data-e2e="comment-list"], [data-e2e="search-box"], textarea, input, [contenteditable="true"]')) {
            return;
        }

        accumulatedDelta += e.deltaY;

        if (accumulatedDelta >= THRESHOLD) {
            accumulatedDelta = 0;
            if (navigate('next')) {
                e.preventDefault();
                e.stopPropagation();
            }
        } else if (accumulatedDelta <= -THRESHOLD) {
            accumulatedDelta = 0;
            if (navigate('prev')) {
                e.preventDefault();
                e.stopPropagation();
            }
        }

        clearTimeout(window.__tt_wheel_timer);
        window.__tt_wheel_timer = setTimeout(() => { accumulatedDelta = 0; }, 180);
    }, { passive: false, capture: true });

    // Global keyboard navigation bridge
    window.addEventListener('keydown', (e) => {
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)) {
            return;
        }
        if (e.key === 'ArrowDown' || e.key === 'PageDown' || e.key === 'j' || e.key === 's') {
            if (navigate('next')) e.preventDefault();
        } else if (e.key === 'ArrowUp' || e.key === 'PageUp' || e.key === 'k' || e.key === 'w') {
            if (navigate('prev')) e.preventDefault();
        } else if (e.key === ' ' || e.code === 'Space') {
            const v = document.querySelector('video');
            if (v) {
                if (v.paused) v.play().catch(() => {});
                else v.pause();
                e.preventDefault();
            }
        } else if (e.key === 'm' || e.key === 'M') {
            const muteBtn = document.querySelector('[data-e2e="video-sound"]');
            if (muteBtn && typeof muteBtn.click === 'function') muteBtn.click();
        }
    }, { capture: true });

    // Auto-skip sponsored / promotional ad cards in feed
    setInterval(() => {
        const adTag = document.querySelector('[data-e2e="ad-tag"], [data-e2e="feed-ad"]');
        if (adTag) {
            const container = adTag.closest('[data-e2e="recommend-list-item-container"], div[class*="DivItemContainer"]');
            if (container) {
                navigate('next');
            }
        }
    }, 600);
})();
"""


# Auto-focus the chat input field gently on page load for AI chat apps
FOCUS_SCRIPT = """
(function() {
    function focusChat() {
        const input = document.querySelector(
            '#prompt-textarea, textarea[tabindex="0"], textarea, [contenteditable="true"]'
        );
        if (input && document.activeElement !== input) {
            input.focus();
            return true;
        }
        return false;
    }

    let count = 0;
    const interval = setInterval(() => {
        count++;
        if (focusChat() || count > 15) {
            clearInterval(interval);
        }
    }, 250);
})();
"""

# Track LLM streaming/generation state and notify host when complete
GENERATION_SCRIPT = """
(function() {
    let wasGenerating = false;
    let stableCount = 0;

    function isStreaming() {
        const stopBtn = document.querySelector(
            'button[data-testid="stop-button"], ' +
            'button[aria-label*="Stop"], ' +
            'button[aria-label*="Arrêter"], ' +
            'button[aria-label*="Berhenti"], ' +
            'button[data-testid*="stop"]'
        );
        if (stopBtn) return true;

        if (document.querySelector('.result-streaming, [data-is-streaming="true"]')) {
            return true;
        }

        const rectIcon = document.querySelector('button svg rect');
        if (rectIcon && rectIcon.closest('button')) return true;

        return false;
    }

    function checkLoop() {
        const generating = isStreaming();
        if (generating) {
            wasGenerating = true;
            stableCount = 0;
        } else if (wasGenerating) {
            stableCount++;
            if (stableCount >= 2) {
                wasGenerating = false;
                stableCount = 0;
                if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.generation_done) {
                    window.webkit.messageHandlers.generation_done.postMessage("done");
                }
            }
        }
    }

    setInterval(checkLoop, 300);
})();
"""

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")


class Web2GtkWindow(Adw.ApplicationWindow):
    def __init__(self, app, manifest):
        super().__init__(application=app, title=manifest.name)
        self.app = app
        self.manifest = manifest
        self.config_file = os.path.join(self.manifest.config_dir, "window_state.json")

        # Window sizing & state
        state = self.load_window_state()
        self.set_default_size(state.get("width", 1080), state.get("height", 800))
        if state.get("is_maximized", False):
            self.maximize()

        # Tray notification dedup state
        self._last_notified_title = None
        self.connect("notify::visible", self.on_visibility_changed)

        # Intercept close request
        self.connect("close-request", self.on_close_request)

        # Persistent Network Session
        if self.manifest.persistent_storage:
            os.makedirs(self.manifest.data_dir, exist_ok=True)
            os.makedirs(self.manifest.cache_dir, exist_ok=True)
            self.session = WebKit.NetworkSession.new(
                data_directory=self.manifest.data_dir,
                cache_directory=self.manifest.cache_dir
            )
            # Persistent SQLite cookies
            cookie_file = os.path.join(self.manifest.data_dir, "cookies.sqlite")
            cookie_manager = self.session.get_cookie_manager()
            cookie_manager.set_accept_policy(WebKit.CookieAcceptPolicy.ALWAYS)
            cookie_manager.set_persistent_storage(
                cookie_file, WebKit.CookiePersistentStorage.SQLITE
            )
        else:
            self.session = WebKit.NetworkSession.new_ephemeral()
            cookie_manager = self.session.get_cookie_manager()
            cookie_manager.set_accept_policy(WebKit.CookieAcceptPolicy.ALWAYS)

        # Disable ITP for reliable cross-origin auth flows
        self.session.set_itp_enabled(False)

        # WebKit Settings & GPU Hardware Acceleration
        self.settings = WebKit.Settings()
        self.settings.set_user_agent(self.manifest.user_agent)
        self.settings.set_enable_developer_extras(True)
        self.settings.set_enable_webrtc(True)
        self.settings.set_enable_media_stream(True)
        self.settings.set_javascript_can_access_clipboard(True)
        self.settings.set_javascript_can_open_windows_automatically(True)

        # Performance & GPU hardware acceleration
        self.settings.set_hardware_acceleration_policy(WebKit.HardwareAccelerationPolicy.ALWAYS)
        # TikTok feed relies on discrete snap actions; disable smooth scrolling interpolation to prevent micro-delta lag
        if is_tiktok_app(self.manifest.url):
            self.settings.set_enable_smooth_scrolling(False)
        else:
            self.settings.set_enable_smooth_scrolling(True)
        # Disable experimental 2D canvas acceleration on Linux to prevent GPU sync stalls on canvas web apps (Chess.com, etc.)
        self.settings.set_enable_2d_canvas_acceleration(False)
        self.settings.set_enable_webgl(True)
        self.settings.set_enable_media(True)
        self.settings.set_enable_mediasource(True)
        self.settings.set_enable_media_capabilities(True)
        self.settings.set_media_playback_allows_inline(True)
        self.settings.set_media_playback_requires_user_gesture(False)

        # User Content Manager
        self.user_content_manager = WebKit.UserContentManager()
        if self.manifest.stealth:
            stealth_script = WebKit.UserScript(
                source=STEALTH_SCRIPT,
                injected_frames=WebKit.UserContentInjectedFrames.ALL_FRAMES,
                injection_time=WebKit.UserScriptInjectionTime.START
            )
            self.user_content_manager.add_script(stealth_script)

        # Only inject LLM-specific chat helpers (auto-focus and generation done signals) for AI chat apps
        if is_llm_chat_app(self.manifest.url):
            focus_user_script = WebKit.UserScript(
                source=FOCUS_SCRIPT,
                injected_frames=WebKit.UserContentInjectedFrames.ALL_FRAMES,
                injection_time=WebKit.UserScriptInjectionTime.END
            )
            self.user_content_manager.add_script(focus_user_script)

            generation_user_script = WebKit.UserScript(
                source=GENERATION_SCRIPT,
                injected_frames=WebKit.UserContentInjectedFrames.ALL_FRAMES,
                injection_time=WebKit.UserScriptInjectionTime.END
            )
            self.user_content_manager.add_script(generation_user_script)
            self.user_content_manager.register_script_message_handler("generation_done")
            self.user_content_manager.connect(
                "script-message-received::generation_done",
                self.on_generation_done
            )

        # TikTok-specific feed scrolling & navigation bridge
        if is_tiktok_app(self.manifest.url):
            tiktok_user_script = WebKit.UserScript(
                source=TIKTOK_OPTIMIZATION_SCRIPT,
                injected_frames=WebKit.UserContentInjectedFrames.ALL_FRAMES,
                injection_time=WebKit.UserScriptInjectionTime.END
            )
            self.user_content_manager.add_script(tiktok_user_script)

        # Setup built-in adblocking & YouTube ad-skipping
        if getattr(self.manifest, "adblock", True):
            setup_adblock(self.user_content_manager, self.manifest.cache_dir, self.manifest.url)

        # Ensure keyboard focus is on web_view when window becomes active
        self.connect("notify::is-active", self.on_window_active_changed)

        # Main Layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # HeaderBar
        self.header_bar = Adw.HeaderBar()
        self.header_bar.add_css_class("flat")
        self.main_box.append(self.header_bar)

        # Title widget
        parsed_url = urlparse(self.manifest.url)
        self.title_widget = Adw.WindowTitle(
            title=self.manifest.name,
            subtitle=parsed_url.netloc or self.manifest.url
        )
        self.header_bar.set_title_widget(self.title_widget)

        # Nav buttons
        self.nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.header_bar.pack_start(self.nav_box)

        self.btn_back = Gtk.Button(icon_name="go-previous-symbolic")
        self.btn_back.set_tooltip_text("Kembali (Alt+Left)")
        self.btn_back.connect("clicked", self.on_back_clicked)
        self.btn_back.set_sensitive(False)
        self.nav_box.append(self.btn_back)

        self.btn_forward = Gtk.Button(icon_name="go-next-symbolic")
        self.btn_forward.set_tooltip_text("Maju (Alt+Right)")
        self.btn_forward.connect("clicked", self.on_forward_clicked)
        self.btn_forward.set_sensitive(False)
        self.nav_box.append(self.btn_forward)

        self.btn_reload = Gtk.Button(icon_name="view-refresh-symbolic")
        self.btn_reload.set_tooltip_text("Muat Ulang (Ctrl+R)")
        self.btn_reload.connect("clicked", self.on_reload_clicked)
        self.nav_box.append(self.btn_reload)

        self.btn_home = Gtk.Button(icon_name="go-home-symbolic")
        self.btn_home.set_tooltip_text(f"Beranda {self.manifest.name}")
        self.btn_home.connect("clicked", lambda _: self.web_view.load_uri(self.manifest.url))
        self.nav_box.append(self.btn_home)

        # Menu Button
        self.menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.menu_btn.set_tooltip_text("Menu Aplikasi")
        self.header_bar.pack_end(self.menu_btn)
        self.setup_menu()

        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.add_css_class("osd")
        self.progress_bar.set_visible(False)
        self.main_box.append(self.progress_bar)

        # Primary WebView
        self.web_view = WebKit.WebView(
            network_session=self.session,
            user_content_manager=self.user_content_manager
        )
        self.web_view.set_settings(self.settings)
        self.web_view.set_vexpand(True)
        self.web_view.set_hexpand(True)
        self.main_box.append(self.web_view)

        # Connect signals
        self.web_view.connect("notify::estimated-load-progress", self.on_progress_changed)
        self.web_view.connect("notify::title", self.on_title_changed)
        self.web_view.connect("notify::uri", self.on_uri_changed)
        self.web_view.connect("load-changed", self.on_load_changed)
        self.web_view.connect("load-failed", self.on_load_failed)
        self.web_view.connect("create", self.on_create_popup)
        self.web_view.connect("permission-request", self.on_permission_request)
        self.web_view.connect("show-notification", self.on_show_notification)
        self.web_view.connect("decide-policy", self.on_decide_policy)
        self.session.connect("download-started", self.on_download_started)

        # Keyboard shortcuts
        self.setup_shortcuts()

        # Initial Load
        GLib.idle_add(lambda: self.web_view.load_uri(self.manifest.url))

    def setup_menu(self):
        menu = Gio.Menu()

        view_section = Gio.Menu()
        view_section.append("Perbesar (Ctrl++)", "app.zoom_in")
        view_section.append("Perkecil (Ctrl+-)", "app.zoom_out")
        view_section.append("Reset Zoom (Ctrl+0)", "app.zoom_reset")
        menu.append_section(None, view_section)

        tools_section = Gio.Menu()
        tools_section.append("Salin URL Halaman", "app.copy_url")
        tools_section.append("Buka Web Inspector (F12)", "app.inspect")
        tools_section.append("Hapus Cache", "app.clear_cache")
        menu.append_section(None, tools_section)

        app_section = Gio.Menu()
        app_section.append(f"Tentang {self.manifest.name}", "app.about")
        if self.manifest.system_tray:
            app_section.append("Sembunyikan ke Tray", "app.hide_to_tray")
        app_section.append("Keluar (Ctrl+Q)", "app.quit")
        menu.append_section(None, app_section)

        self.menu_btn.set_menu_model(menu)

    def setup_shortcuts(self):
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)

    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        alt = (state & Gdk.ModifierType.ALT_MASK) != 0

        if ctrl:
            if keyval in (Gdk.KEY_r, Gdk.KEY_R):
                self.web_view.reload()
                return True
            elif keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
                self.zoom_in()
                return True
            elif keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
                self.zoom_out()
                return True
            elif keyval in (Gdk.KEY_0, Gdk.KEY_KP_0):
                self.zoom_reset()
                return True
            elif keyval in (Gdk.KEY_q, Gdk.KEY_Q):
                self.app.quit()
                return True
            elif keyval in (Gdk.KEY_w, Gdk.KEY_W):
                if self.manifest.system_tray:
                    self.set_visible(False)
                else:
                    self.close()
                return True
        elif alt:
            if keyval == Gdk.KEY_Left:
                if self.web_view.can_go_back():
                    self.web_view.go_back()
                return True
            elif keyval == Gdk.KEY_Right:
                if self.web_view.can_go_forward():
                    self.web_view.go_forward()
                return True
        elif keyval == Gdk.KEY_F11:
            if self.is_fullscreen():
                self.unfullscreen()
            else:
                self.fullscreen()
            return True
        elif keyval == Gdk.KEY_F12:
            inspector = self.web_view.get_inspector()
            if inspector.is_attached():
                inspector.close()
            else:
                inspector.show()
            return True

        return False

    def zoom_in(self):
        level = self.web_view.get_zoom_level()
        self.web_view.set_zoom_level(min(level + 0.1, 3.0))

    def zoom_out(self):
        level = self.web_view.get_zoom_level()
        self.web_view.set_zoom_level(max(level - 0.1, 0.5))

    def zoom_reset(self):
        self.web_view.set_zoom_level(1.0)

    def on_back_clicked(self, _):
        if self.web_view.can_go_back():
            self.web_view.go_back()

    def on_forward_clicked(self, _):
        if self.web_view.can_go_forward():
            self.web_view.go_forward()

    def on_reload_clicked(self, _):
        self.web_view.reload()

    def on_progress_changed(self, web_view, _):
        progress = web_view.get_estimated_load_progress()
        self.progress_bar.set_fraction(progress)
        self.progress_bar.set_visible(progress < 1.0)

    def on_title_changed(self, web_view, _):
        title = web_view.get_title()
        if title:
            self.title_widget.set_title(title)
            self.set_title(title)

            # Tray notification: send native GNOME notification when window is hidden
            if not self.get_visible() and title != self._last_notified_title:
                self._last_notified_title = title
                match = re.match(r"^[\(\u2022\s]*(\d+)[\)\s\u2022]", title)
                body = f"{match.group(1)} new messages" if match else title
                notif = Gio.Notification.new(self.manifest.name)
                notif.set_body(body)
                notif.set_priority(Gio.NotificationPriority.HIGH)
                self.app.send_notification(f"{self.manifest.slug}-reply", notif)

    def on_visibility_changed(self, *_):
        if self.get_visible():
            self._last_notified_title = None
            self.app.withdraw_notification(f"{self.manifest.slug}-reply")

    def on_uri_changed(self, web_view, _):
        uri = web_view.get_uri()
        if uri:
            try:
                host = urlparse(uri).netloc
                self.title_widget.set_subtitle(host if host else self.manifest.name)
            except Exception:
                pass

    def send_desktop_notification(self, summary, body, urgency=2):
        """Send desktop notification via direct D-Bus with fallback to GApplication."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                None
            )
            hints = {
                "desktop-entry": GLib.Variant("s", self.manifest.slug),
                "urgency": GLib.Variant("y", urgency),
            }
            proxy.Notify(
                "(susssasa{sv}i)",
                self.manifest.name,
                0,
                self.manifest.icon,
                summary,
                body,
                [],
                hints,
                6000
            )
            print(f"[{self.manifest.slug}] Desktop notification sent: {summary} - {body}")
        except Exception as e:
            print(f"[{self.manifest.slug}] D-Bus notification error: {e}")

        try:
            notif = Gio.Notification.new(summary)
            notif.set_body(body)
            notif.set_priority(Gio.NotificationPriority.HIGH)
            self.app.send_notification(f"{self.manifest.slug}-notify", notif)
        except Exception:
            pass

    def on_window_active_changed(self, *_):
        if self.is_active():
            self.web_view.grab_focus()
            if hasattr(self, "tray") and self.tray:
                self.tray.set_attention(False)

    def on_show_notification(self, web_view, notification):
        title = notification.get_title() or self.manifest.name
        body = notification.get_body() or ""
        self.send_desktop_notification(title, body, urgency=1)
        return True

    def on_generation_done(self, manager, js_result):
        print(f"[{self.manifest.slug}] Response generation finished!")
        if not self.is_active() or not self.get_visible():
            self.send_desktop_notification(
                summary=self.manifest.name,
                body="Response completed",
                urgency=2
            )
            if hasattr(self, "tray") and self.tray:
                self.tray.set_attention(True, f"{self.manifest.name}: Response completed")

    def on_decide_policy(self, web_view, decision, decision_type):
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            if not decision.is_mime_type_supported():
                decision.download()
                return True
        return False

    def on_load_changed(self, web_view, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            self.progress_bar.set_visible(False)
            self.btn_back.set_sensitive(web_view.can_go_back())
            self.btn_forward.set_sensitive(web_view.can_go_forward())
            self.web_view.grab_focus()

    def on_load_failed(self, web_view, load_event, failing_uri, error):
        """Ignore navigation cancellations (e.g. client redirects, pushState) to avoid error pages."""
        if getattr(error, "code", None) == 302 or "cancelled" in str(error).lower():
            return True
        return False

    def on_create_popup(self, web_view, navigation_action):
        """Handle popup windows (OAuth logins) and route external links to default browser."""
        req = navigation_action.get_request()
        uri = req.get_uri() if req else None

        # External non-auth links open directly in system browser
        if uri and uri not in ("about:blank", ""):
            if not is_auth_url(uri) and not is_same_app_domain(uri, self.manifest.url):
                try:
                    Gio.AppInfo.launch_default_for_uri(uri, None)
                except Exception as e:
                    print(f"[{self.manifest.slug}] Error launching default browser: {e}")
                return None

        popup = Adw.Window(transient_for=self, modal=False)
        popup.set_default_size(520, 680)

        popup_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popup.set_content(popup_box)

        popup_header = Adw.HeaderBar()
        popup_header.add_css_class("flat")
        popup_title = Adw.WindowTitle(title="Login")
        popup_header.set_title_widget(popup_title)
        popup_box.append(popup_header)

        # Related view automatically inherits the parent view's network session
        popup_web_view = WebKit.WebView(
            related_view=web_view,
            user_content_manager=self.user_content_manager
        )
        popup_web_view.set_settings(self.settings)
        popup_web_view.set_vexpand(True)
        popup_web_view.set_hexpand(True)
        popup_box.append(popup_web_view)

        def on_popup_decide_policy(wv, decision, decision_type):
            if decision_type == WebKit.PolicyDecisionType.NAVIGATION_ACTION:
                nav_action = decision.get_navigation_action()
                target_req = nav_action.get_request()
                target_uri = target_req.get_uri() if target_req else None
                if target_uri and target_uri not in ("about:blank", ""):
                    if not is_auth_url(target_uri) and not is_same_app_domain(target_uri, self.manifest.url):
                        try:
                            Gio.AppInfo.launch_default_for_uri(target_uri, None)
                        except Exception as e:
                            print(f"[{self.manifest.slug}] Error launching default browser: {e}")
                        decision.ignore()
                        popup.close()
                        return True
            elif decision_type == WebKit.PolicyDecisionType.RESPONSE:
                if not decision.is_mime_type_supported():
                    decision.download()
                    popup.close()
                    return True
            return False

        popup_web_view.connect("decide-policy", on_popup_decide_policy)
        popup_web_view.connect(
            "notify::title",
            lambda wv, _: popup_title.set_title(wv.get_title() or "Login")
        )
        popup_web_view.connect("close", lambda _: popup.close())

        popup.present()
        return popup_web_view

    def on_permission_request(self, web_view, request):
        if isinstance(request, (WebKit.UserMediaPermissionRequest,
                                WebKit.DeviceInfoPermissionRequest,
                                WebKit.NotificationPermissionRequest)):
            request.allow()
            return True
        return False

    def on_download_started(self, session, download):
        """Route downloads to ~/Downloads with non-clobbering filenames."""
        def on_decide_destination(dl, suggested_filename):
            try:
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                filename = suggested_filename or "download"
                dest_path = os.path.join(DOWNLOAD_DIR, filename)
                base, ext = os.path.splitext(dest_path)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = f"{base} ({counter}){ext}"
                    counter += 1

                # WebKitDownload expects a native absolute path, NOT a file:// URI
                dl.set_destination(dest_path)

                def on_finished(d):
                    filename = os.path.basename(dest_path)
                    print(f"[{self.manifest.slug}] Download finished: {dest_path}")
                    self.send_desktop_notification(
                        summary="Download Complete",
                        body=f"{filename} saved to ~/Downloads",
                        urgency=2
                    )
                    if hasattr(self, "tray") and self.tray:
                        self.tray.set_attention(True, f"Download: {filename}")

                dl.connect("finished", on_finished)
                dl.connect(
                    "failed",
                    lambda d, err: print(f"[{self.manifest.slug}] Download failed: {err.message}")
                )
            except Exception as e:
                print(f"[{self.manifest.slug}] Download error: {e}")
            return True

        download.connect("decide-destination", on_decide_destination)

    def load_window_state(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return self.manifest.window or {"width": 1080, "height": 800, "is_maximized": False}

    def save_window_state(self):
        try:
            os.makedirs(self.manifest.config_dir, exist_ok=True)
            data = {
                "width": self.get_width(),
                "height": self.get_height(),
                "is_maximized": self.is_maximized()
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def on_close_request(self, _):
        self.save_window_state()
        if getattr(self.manifest, "close_to_tray", False):
            self.set_visible(False)
            return True
        self.app.quit()
        return False
