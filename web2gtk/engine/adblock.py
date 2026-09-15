"""
Built-in Adblocker & Content Filtering Engine for web2gtk.
Supports native WebKit declarative content filters, cosmetic stylesheet injection,
and high-speed non-destructive YouTube ad skipping.
"""

import os
import json
import tempfile
import gi

gi.require_version('WebKit', '6.0')
gi.require_version('Gio', '2.0')
gi.require_version('GLib', '2.0')

from gi.repository import WebKit, Gio, GLib

# Declarative WebKit content filtering rules for known ad and tracker networks
COMMON_AD_RULES = [
    {"trigger": {"url-filter": r".*doubleclick\.net/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*googlesyndication\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*googleadservices\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*adnxs\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*criteo\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*taboola\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*outbrain\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*scorecardresearch\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*amazon-adsystem\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*pubmatic\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*rubiconproject\.com/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*adservice\.google\..*"}, "action": {"type": "block"}},
]

# YouTube-specific cosmetic ad hiding CSS
YOUTUBE_COSMETIC_CSS = """
#masthead-ad,
ytd-ad-slot-renderer,
ytd-rich-item-renderer:has(ytd-ad-slot-renderer),
.ytp-ad-overlay-container,
.ytp-ad-message-container,
.ytp-ad-overlay-slot,
.ytp-ad-overlay-image,
.ytp-ad-action-interstitial,
.ytp-ad-player-overlay-layout,
ytd-promoted-sparkles-web-renderer,
ytd-banner-promo-renderer,
#player-ads,
ytd-in-feed-ad-layout-renderer,
ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-ads"],
ytd-enforcement-message-view-model,
tp-yt-iron-overlay-backdrop[opened] {
    display: none !important;
}
"""

# YouTube non-intrusive safe ad skipper:
# 1. Instantly clicks all modern/legacy Skip buttons with native pointer & mouse event sequence.
# 2. Silences ad audio immediately (video.muted = true).
# 3. Accelerates ad playback to 16x speed without ever mutating video.currentTime (prevents anti-adblock violation and GStreamer seek crashes).
# 4. Auto-dismisses consent and interstitial popups.
# 5. Listens reactively via MutationObserver and polling interval.
YOUTUBE_ADBLOCK_SCRIPT = """
(function() {
    let adMuted = false;

    function triggerClick(el) {
        if (!el) return;
        try { el.click(); } catch(e) {}
        try {
            const rect = el.getBoundingClientRect();
            const clientX = rect.left + rect.width / 2;
            const clientY = rect.top + rect.height / 2;
            const opts = {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: clientX,
                clientY: clientY,
                button: 0,
                buttons: 1
            };
            el.dispatchEvent(new PointerEvent('pointerdown', opts));
            el.dispatchEvent(new MouseEvent('mousedown', opts));
            el.dispatchEvent(new PointerEvent('pointerup', opts));
            el.dispatchEvent(new MouseEvent('mouseup', opts));
            el.dispatchEvent(new MouseEvent('click', opts));
        } catch(e) {}
    }

    function clickSkipButtons() {
        const selectors = [
            '.ytp-skip-ad-button',
            '.ytp-ad-skip-button',
            '.ytp-ad-skip-button-modern',
            '.ytp-ad-skip-button-container',
            '.ytp-ad-skip-button-slot button',
            'button.ytp-ad-skip-button',
            'button.ytp-ad-skip-button-modern',
            '[class*="skip-button"]',
            '[class*="skip-ad-button"]',
            '[id*="skip-button"]',
            'button.ytp-ad-overlay-close-button',
            '.ytp-ad-overlay-close-button',
            '.ytp-ad-overlay-slot .ytp-ad-overlay-close-button',
            'button[aria-label*="skip" i]',
            'button[aria-label*="lewati" i]',
            '[class*="ytp-ad-skip"]'
        ];

        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            for (const el of els) {
                triggerClick(el);
            }
        }

        // Generic text scan inside player for any button containing "skip" or "lewati"
        const player = document.querySelector('#movie_player, .html5-video-player');
        if (player) {
            const candidates = player.querySelectorAll('button, [role="button"], div[class*="button"]');
            for (const btn of candidates) {
                const text = (btn.textContent || '').trim().toLowerCase();
                if (text === 'skip' || text.startsWith('skip ') || text === 'lewati' || text.startsWith('lewati ') || text === 'skip ad' || text === 'skip ads') {
                    triggerClick(btn);
                }
            }
        }

        // Auto-dismiss anti-adblock or confirmation dialogs
        const dismissSelectors = [
            'tp-yt-paper-dialog #dismiss-button',
            '#dismiss-button',
            '.style-scope.yt-confirm-dialog-renderer',
            'ytd-enforcement-message-view-model #dismiss-button',
            'yt-button-renderer#dismiss-button'
        ];
        for (const sel of dismissSelectors) {
            const btn = document.querySelector(sel);
            if (btn) triggerClick(btn);
        }

        // Remove enforcement model & backdrop if present
        const enforcement = document.querySelector('ytd-enforcement-message-view-model');
        if (enforcement) {
            enforcement.remove();
            const backdrop = document.querySelector('tp-yt-iron-overlay-backdrop[opened]');
            if (backdrop) backdrop.remove();
            const video = document.querySelector('video');
            if (video && video.paused) video.play().catch(() => {});
        }
    }

    function handleVideoAd() {
        const player = document.querySelector('#movie_player, .html5-video-player');
        if (!player) return;

        const isAd = player.classList.contains('ad-showing') || 
                     player.classList.contains('ad-interrupting') ||
                     document.querySelector('.ytp-ad-player-overlay, .ytp-ad-preview-container, .ytp-ad-text') !== null;
        const video = player.querySelector('video.html5-main-video, video');

        if (isAd && video) {
            // Mute ad audio so user hears nothing
            if (!video.muted) {
                video.muted = true;
                adMuted = true;
            }
            // Accelerate ad playback so it finishes in milliseconds without touching currentTime
            if (video.playbackRate < 16.0) {
                video.playbackRate = 16.0;
            }
            // Resume if paused by ad injection
            if (video.paused) {
                video.play().catch(() => {});
            }
            clickSkipButtons();
        } else if (adMuted && video) {
            // Ad ended: restore user audio and playback speed immediately
            adMuted = false;
            video.muted = false;
            if (video.playbackRate > 2.0) {
                video.playbackRate = 1.0;
            }
        }
    }

    // Fast polling fallback (100ms)
    setInterval(() => {
        clickSkipButtons();
        handleVideoAd();
    }, 100);

    // Reactive DOM observer for immediate response to ad class or button injection
    function setupObserver() {
        const target = document.querySelector('#movie_player, .html5-video-player, ytd-app') || document.body;
        if (!target) return;
        const observer = new MutationObserver(() => {
            clickSkipButtons();
            handleVideoAd();
        });
        observer.observe(target, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['class', 'src']
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupObserver);
    } else {
        setupObserver();
    }
})();
"""


def setup_adblock(user_content_manager: WebKit.UserContentManager, cache_dir: str, target_url: str):
    """Compile and apply adblocking rules and scripts to WebKit UserContentManager."""
    is_youtube = "youtube.com" in (target_url or "").lower()

    # 1. YouTube specific ad skipper & cosmetic stylesheet
    if is_youtube:
        yt_script = WebKit.UserScript(
            source=YOUTUBE_ADBLOCK_SCRIPT,
            injected_frames=WebKit.UserContentInjectedFrames.ALL_FRAMES,
            injection_time=WebKit.UserScriptInjectionTime.START
        )
        user_content_manager.add_script(yt_script)

        yt_style = WebKit.UserStyleSheet(
            source=YOUTUBE_COSMETIC_CSS,
            injected_frames=WebKit.UserContentInjectedFrames.ALL_FRAMES,
            level=WebKit.UserStyleLevel.USER,
            allow_list=None,
            block_list=None
        )
        user_content_manager.add_style_sheet(yt_style)

    # 2. Native WebKit Content Filter Store with automatic hash-based cache invalidation
    filter_dir = os.path.join(cache_dir, "adblock_filters")
    os.makedirs(filter_dir, exist_ok=True)
    store = WebKit.UserContentFilterStore.new(filter_dir)

    import hashlib
    rules_hash = hashlib.md5(json.dumps(COMMON_AD_RULES, sort_keys=True).encode()).hexdigest()[:8]
    filter_id = f"web2gtk_filter_{rules_hash}"

    def on_filter_saved(s, res, _):
        try:
            compiled_filter = s.save_from_file_finish(res)
            if compiled_filter:
                user_content_manager.add_filter(compiled_filter)
        except Exception:
            pass

    def on_filter_loaded(s, res, _):
        try:
            compiled_filter = s.load_finish(res)
            if compiled_filter:
                user_content_manager.add_filter(compiled_filter)
        except Exception:
            compile_rules()

    def compile_rules():
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(COMMON_AD_RULES, f)
                tmp_rules_file = f.name

            gfile = Gio.File.new_for_path(tmp_rules_file)
            store.save_from_file(filter_id, gfile, None, on_filter_saved, None)
        except Exception:
            pass

    try:
        store.load(filter_id, None, on_filter_loaded, None)
    except Exception:
        compile_rules()
