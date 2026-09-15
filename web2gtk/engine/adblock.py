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

# YouTube safe ad skipper: mutes ad audio, instantly clicks skip buttons, fast-skips short ads,
# and dismisses interstitial dialogs without tampering with JS global prototypes or main video buffers
YOUTUBE_ADBLOCK_SCRIPT = """
(function() {
    let adMuted = false;

    function clickSkipButtons() {
        const selectors = [
            '.ytp-skip-ad-button',
            '.ytp-ad-skip-button',
            '.ytp-ad-skip-button-modern',
            '.ytp-ad-skip-button-slot button',
            'button.ytp-ad-skip-button',
            'button.ytp-ad-overlay-close-button',
            '.ytp-ad-overlay-close-button',
            '.ytp-ad-overlay-slot .ytp-ad-overlay-close-button'
        ];
        for (const sel of selectors) {
            const btn = document.querySelector(sel);
            if (btn && typeof btn.click === 'function') {
                btn.click();
            }
        }
        const dismiss = document.querySelector('tp-yt-paper-dialog #dismiss-button, #dismiss-button, .style-scope.yt-confirm-dialog-renderer');
        if (dismiss && typeof dismiss.click === 'function') {
            dismiss.click();
        }
    }

    function handleVideoAd() {
        const player = document.querySelector('#movie_player, .html5-video-player');
        if (!player) return;

        const isAd = player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting');
        const video = player.querySelector('video.html5-main-video, video');

        if (isAd && video) {
            // Mute ad audio so user hears nothing
            if (!video.muted) {
                video.muted = true;
                adMuted = true;
            }
            // Safely advance only if ad video has buffered data (readyState >= 3)
            // Never touch currentTime during seek or buffering state
            if (video.readyState >= 3 && isFinite(video.duration) && video.duration > 0 && video.duration <= 180) {
                if (video.currentTime < video.duration) {
                    video.currentTime = video.duration;
                }
            }
            clickSkipButtons();
        } else if (adMuted && video) {
            // Ad ended, restore audio
            adMuted = false;
            video.muted = false;
        }
    }

    setInterval(() => {
        clickSkipButtons();
        handleVideoAd();
    }, 100);
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
            injection_time=WebKit.UserScriptInjectionTime.END
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

