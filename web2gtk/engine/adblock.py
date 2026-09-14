"""
Built-in Adblocker & Content Filtering Engine for web2gtk.
Supports native WebKit declarative content filters and dynamic YouTube ad-skipping.
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
    {"trigger": {"url-filter": r".*youtube\.com/pagead/.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*youtube\.com/api/stats/ads.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*youtube\.com/ptracking.*"}, "action": {"type": "block"}},
    {"trigger": {"url-filter": r".*youtube\.com/youtubei/v1/player/ad_break.*"}, "action": {"type": "block"}},
]

# YouTube-specific cosmetic ad hiding CSS
YOUTUBE_COSMETIC_CSS = """
#masthead-ad,
ytd-ad-slot-renderer,
ytd-rich-item-renderer:has(ytd-ad-slot-renderer),
.ytp-ad-overlay-container,
.ytp-ad-message-container,
ytd-promoted-sparkles-web-renderer,
ytd-banner-promo-renderer,
#player-ads,
.video-ads,
.ytp-ad-module,
ytd-in-feed-ad-layout-renderer,
ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-ads"] {
    display: none !important;
}
"""

# Dynamic high-speed YouTube ad stripper & non-destructive fast-forward script
YOUTUBE_ADBLOCK_SCRIPT = """
(function() {
    // 1. Prune ad placements from initial player response and API payloads before player loads
    function pruneAds(obj) {
        if (!obj || typeof obj !== 'object') return obj;
        delete obj.adPlacements;
        delete obj.adSlots;
        delete obj.playerAds;
        delete obj.adBreakHeartbeatParams;
        if (obj.playerResponse && typeof obj.playerResponse === 'object') {
            delete obj.playerResponse.adPlacements;
            delete obj.playerResponse.adSlots;
            delete obj.playerResponse.playerAds;
        }
        return obj;
    }

    try {
        const origParse = JSON.parse;
        JSON.parse = function(...args) {
            const res = origParse.apply(this, args);
            return pruneAds(res);
        };

        let _ytPlayerResponse = undefined;
        Object.defineProperty(window, 'ytInitialPlayerResponse', {
            configurable: true,
            enumerable: true,
            get() { return _ytPlayerResponse; },
            set(val) {
                _ytPlayerResponse = pruneAds(val);
            }
        });
    } catch(e) {}

    // 2. Runtime fallback: fast-forward without seeking (seeking causes YouTube anti-adblock pause)
    let weMuted = false;
    let lastAd = false;

    function handleAds() {
        const player = document.querySelector('#movie_player, .html5-video-player');
        const video = document.querySelector('#movie_player video, video.html5-main-video, video');
        if (!player || !video) return;

        const isAd = player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting');

        if (isAd) {
            lastAd = true;
            // Mute during ad
            if (!video.muted) {
                video.muted = true;
                weMuted = true;
            }
            // Accelerate without seeking (YouTube rejects seek but allows high playback rate)
            if (video.playbackRate < 16.0) {
                video.playbackRate = 16.0;
            }

            // Immediately click any skip button if available
            const skipButtons = document.querySelectorAll(
                '.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button-slot button, button.ytp-ad-skip-button'
            );
            for (const btn of skipButtons) {
                if (btn && typeof btn.click === 'function') {
                    btn.click();
                }
            }

            // If YouTube paused the video, resume playback automatically
            if (video.paused) {
                video.play().catch(() => {});
            }
        } else if (lastAd) {
            // Ad ended: restore audio and normal speed immediately
            lastAd = false;
            if (weMuted) {
                video.muted = false;
                weMuted = false;
            }
            video.playbackRate = 1.0;
            if (video.paused) {
                video.play().catch(() => {});
            }
        }

        // Dismiss interstitial modal overlays
        const dismissBtn = document.querySelector('tp-yt-paper-dialog #dismiss-button, #dismiss-button');
        if (dismissBtn && typeof dismissBtn.click === 'function') {
            dismissBtn.click();
        }
    }

    setInterval(handleAds, 150);
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

    # 2. Native WebKit Content Filter Store
    filter_dir = os.path.join(cache_dir, "adblock_filters")
    os.makedirs(filter_dir, exist_ok=True)
    store = WebKit.UserContentFilterStore.new(filter_dir)

    filter_id = "web2gtk_common_adblock"

    def on_filter_saved(s, res, _):
        try:
            compiled_filter = s.save_from_file_finish(res)
            if compiled_filter:
                user_content_manager.add_filter(compiled_filter)
        except Exception as e:
            # Fallback or already saved
            pass

    def on_filter_loaded(s, res, _):
        try:
            compiled_filter = s.load_finish(res)
            if compiled_filter:
                user_content_manager.add_filter(compiled_filter)
        except Exception:
            # Recompile from rules JSON
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

    # Try loading existing compiled filter first, otherwise compile
    try:
        store.load(filter_id, None, on_filter_loaded, None)
    except Exception:
        compile_rules()
