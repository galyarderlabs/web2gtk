# web2gtk Roadmap

This document outlines the development direction and planned milestones for **web2gtk**.

Our north star is clear: **keep it lightweight, native, and unapologetically Linux/GNOME-first.** We do not aim to support Windows or macOS; our focus is delivering the best native GTK4/Libadwaita desktop experience for web apps without Chromium or Electron bloat.

---

## Current Status: v0.1.0 (Released)

- [x] **GTK4 & Libadwaita Engine**: Pure native look and feel, adaptive CSD titlebar, dark/light theme synchronization.
- [x] **Lightweight Shared WebKit Runtime**: Built on system `webkitgtk-6.0`, requiring only 80–150 MB RAM per instance.
- [x] **Persistent Isolated Storage**: Dedicated SQLite cookie jars (`cookies.sqlite`) and LocalStorage per application.
- [x] **D-Bus System Tray (SNI)**: Support for `org.kde.StatusNotifierItem`, background window hiding, and dynamic attention indicators (`NeedsAttention`).
- [x] **OAuth & Transient Popups**: Dedicated popups for Google, Microsoft, Apple, and GitHub logins without breaking parent session state.
- [x] **Smart Media & Permissions**: Auto-delegated permissions for WebRTC microphone/camera (voice chat in ChatGPT, Google Meet) and desktop notifications.
- [x] **CLI App Management**: Simple and intuitive commands (`create`, `list`, `info`, `run`, `remove`, `export`).
- [x] **Multi-Format Export**: One-command generator for standalone `.tar.gz` installers and Arch Linux `PKGBUILD`.

---

## Phase 1: Distribution & Ecosystem

- [ ] **Official AUR Package**: Publish `web2gtk` to the Arch User Repository (`aur/web2gtk`).
- [ ] **Debian / Ubuntu `.deb` Packaging**: Automate build of `.deb` packages via GitHub Actions.
- [ ] **Flatpak Manifest Export**: Add `web2gtk export <slug> --format flatpak` to generate standalone Flatpak bundle manifests.
- [ ] **Pre-built Standalone App Releases**: Offer curated community app packages (e.g. Claude GTK, Mistral GTK, NotebookLM GTK).

---

## Phase 2: Enhanced Desktop Integration

- [ ] **MPRIS Media Controller**: Integrate media key controls (`Play`, `Pause`, `Next`, `Previous`) and lock screen album art for music and video web apps (Spotify Web, YouTube Music, SoundCloud).
- [ ] **Custom CSS & JS Injection**: Allow optional user stylesheets (`style.css`) and scripts (`script.js`) per application for custom themes or site tweaks.
- [ ] **Custom Proxy Support**: Add `--proxy` configuration in app manifests for users behind corporate firewalls or VPN routing.
- [ ] **Hardware Acceleration Toggles**: Fine-grained controls for WebKit graphics rendering policies when running on diverse GPU configurations.

---

## Phase 3: Optional Native GUI Manager

- [ ] **Native Libadwaita Manager**: An optional visual GUI (`web2gtk-gui`) built with Libadwaita for users who prefer a graphical dashboard:
  - Browse installed web apps with live screenshots and favicons.
  - One-click app creation wizard with instant icon preview.
  - Visual toggle for system tray, persistent storage, and stealth settings.
  - Direct launch and export buttons.

---

## Guiding Principles

1. **Zero Electron**: We will never bundle Chromium or Node.js.
2. **Lean & Fast**: Fast startup times, minimal memory consumption, zero unnecessary runtime dependencies.
3. **GNOME-Centric**: Respect GNOME Human Interface Guidelines (HIG) and Libadwaita styling standards.
