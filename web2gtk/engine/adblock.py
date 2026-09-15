"""
Built-in Adblocker & Content Filtering Engine for web2gtk.
Supports native WebKit declarative content filters, cosmetic stylesheet injection,
and ultra-lightweight YouTube ad skipping without CPU/RAM overhead or seek crashes.
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

# Ultra-lightweight YouTube ad handler:
# - Zero MutationObserver loops to guarantee 0% CPU and zero memory leak
# - Never mutates video.currentTime or calls loadVideoByPlayerVars to prevent seek crashes and anti-adblock errors
# - Auto-clicks skip buttons and mutes ad audio
# - Fast-forwards unskippable bumper ads safely at 16x without decoding stalls
# - Auto-dismisses interstitial and enforcement dialogs
YOUTUBE_ADBLOCK_SCRIPT = """
(function() {
    let wasAd = false;
    let adMuted = false;

    function handleAds() {
        const player = document.querySelector('#movie_player, .html5-video-player');
        const video = document.querySelector('#movie_player video, video.html5-main-video, video');
        if (!player || !video) return;

        const isAd = player.classList.contains('ad-showing') ||
                     player.classList.contains('ad-interrupting') ||
                     Boolean(player.querySelector('.ytp-ad-player-overlay, .ytp-ad-player-overlay-layout'));

        if (isAd) {
            wasAd = true;

            // Mute ad audio so user hears nothing
            if (!video.muted) {
                video.muted = true;
                adMuted = true;
            }

            // Fast-forward ad at 16x speed (finishes 6s bumper ad in ~0.37s)
            try {
                if (video.playbackRate < 16.0) {
                    video.playbackRate = 16.0;
                }
            } catch(e) {
                try { video.playbackRate = 8.0; } catch(e2) {}
            }

            // Ensure ad continues playing to finish fast
            if (video.paused) {
                video.play().catch(function() {});
            }

            // Click skip button immediately when available
            const skipBtn = document.querySelector(
                '.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button-slot button, button.ytp-ad-skip-button, button.ytp-ad-skip-button-modern, .ytp-ad-skip-button-container button, [id^="skip-button"]'
            );
            if (skipBtn && typeof skipBtn.click === 'function') {
                skipBtn.click();
            }
        } else {
            if (wasAd) {
                wasAd = false;
                // Restore audio
                if (adMuted) {
                    video.muted = false;
                    adMuted = false;
                }
                // Restore playback speed
                if (video.playbackRate > 1.0) {
                    video.playbackRate = 1.0;
                }
                if (video.paused) {
                    video.play().catch(function() {});
                }
            } else if (video.playbackRate > 1.0) {
                // Safety guard: ensure regular video never stays accelerated
                video.playbackRate = 1.0;
            }
        }

        // Always click overlay close buttons if present
        const closeBtn = document.querySelector('.ytp-ad-overlay-close-button, button.ytp-ad-overlay-close-button');
        if (closeBtn && typeof closeBtn.click === 'function') {
            closeBtn.click();
        }

        // Dismiss anti-adblock or confirmation dialogs
        const dismiss = document.querySelector('tp-yt-paper-dialog #dismiss-button, #dismiss-button, .style-scope.yt-confirm-dialog-renderer');
        if (dismiss && typeof dismiss.click === 'function') {
            dismiss.click();
        }

        const enforcement = document.querySelector('ytd-enforcement-message-view-model');
        if (enforcement) {
            enforcement.remove();
            const backdrop = document.querySelector('tp-yt-iron-overlay-backdrop');
            if (backdrop) backdrop.remove();
            if (video && video.paused) video.play().catch(function() {});
        }
    }

    // 150ms gentle polling: responsive ad skipping with virtually zero CPU overhead
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
            injected_frames=WebKit.UserContentInjectedFrames.TOP_FRAME,
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
        # Skip raw network content filtering for YouTube to prevent anti-adblock playback crashes
        return

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
