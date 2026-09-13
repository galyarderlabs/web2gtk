# web2gtk

> **Lightweight, native GTK4 / Libadwaita desktop web app generator for Linux.**  
> Turn any web application into a first-class native GNOME desktop app without the bloat of Electron or Chromium.

[![CI / CD](https://github.com/muhamadgalihsaputra/web2gtk/actions/workflows/ci.yml/badge.svg)](https://github.com/muhamadgalihsaputra/web2gtk/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Kenapa web2gtk?

Tool generator web-to-desktop yang ada saat ini (seperti Nativefier atau Pake) biasanya memakan ratusan MB disk dan boros RAM karena membundel seluruh browser Chromium di setiap aplikasi.

`web2gtk` memanfaatkan engine sistem **WebKitGTK 6.0** dan framework **GTK4 + Libadwaita**:

| Fitur | Nativefier (Electron) | Pake (Tauri) | **web2gtk** |
|---|---|---|---|
| **Ukuran App** | 150 MB – 300 MB | 15 MB – 30 MB | **< 1 KB** (shared runtime) |
| **RAM Usage** | 500 MB – 1.2 GB | 150 MB – 300 MB | **80 MB – 150 MB** |
| **Styling** | Web / Custom frame | Web view wrapper | **100% Native Libadwaita** |
| **System Tray** | XEmbed / AppIndicator | Webview Tray | **Pure D-Bus StatusNotifierItem** |
| **Session Persistence** | Chrome Profile | SQLite / Webview | **Isolated SQLite Cookies & Storage** |
| **Anti-Bot / Cloudflare** | Rawan terdeteksi | Sering gagal 2FA | **Safari 18 macOS + Stealth engine** |

---

## Fitur Utama

- **Persistent Auth Across Reboots:** Session token dan cookie tersimpan permanen di SQLite (`cookies.sqlite`). Tidak ada lagi auto-logout setelah reboot.
- **Cloudflare & Bot-Detection Bypass:** Engine WebKit dipasangkan dengan User-Agent Safari macOS, script stealth `navigator.webdriver = false`, dan ITP bypass.
- **D-Bus System Tray:** Berbasis protokol `org.kde.StatusNotifierItem`. Klik close (X) otomatis menyembunyikan app ke tray (StatusNotifierItem), bukan force quit.
- **Auto Icon Scraper:** Otomatis mengambil icon resolusi tinggi (`apple-touch-icon`, web manifest, atau SVG) langsung dari URL target dan meresize ke 32x32, 128x128, dan 256x256 PNG.
- **Full Media & Permissions:** Mendukung WebRTC mikrofon dan kamera (voice chat ChatGPT, Google Meet, dll) serta notifikasi desktop.
- **OAuth Popup Friendly:** Popup login Google / Apple / Microsoft / GitHub berjalan terintegrasi di window transien tanpa kehilangan session parent.

---

## Prasyarat Sistem

Pastikan paket sistem berikut terpasang di distro Linux lu:

### Arch Linux / Manjaro
```bash
sudo pacman -S python-gobject gtk4 libadwaita webkitgtk-6.0 libdbusmenu-glib python-pillow python-requests python-beautifulsoup4 librsvg
```

### Ubuntu / Debian / Fedora
```bash
# Ubuntu 24.04+ / Debian 12+
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0 gir1.2-dbusmenu-glib-0.4 python3-pil python3-requests python3-bs4 librsvg2-bin

# Fedora 39+
sudo dnf install python3-gobject gtk4 libadwaita webkitgtk6.0 libdbusmenu-gtk3 python3-pillow python3-requests python3-beautifulsoup4 librsvg2-tools
```

---

## Instalasi

Clone repositori dan jalankan skrip installer:

```bash
git clone https://github.com/muhamadgalihsaputra/web2gtk.git
cd web2gtk
./install.sh
```

Perintah `web2gtk` dan `web2gtk-runner` akan langsung tersedia di `~/.local/bin/`.

---

## Cara Penggunaan

### 1. Membuat Web App Baru (`create`)

Cukup berikan URL situs target:
```bash
# Otomatis fetch icon & set nama
web2gtk create https://claude.ai --name "Claude"

# Menggunakan icon custom lokal
web2gtk create https://github.com --name "GitHub" --icon ./github.png

# Opsi tanpa system tray
web2gtk create https://notion.so --name "Notion" --no-tray
```

App langsung terintegrasi ke menu aplikasi GNOME (App Grid) dan dapat dijalankan langsung via terminal (misal: `claude-gtk`).

### 2. Melihat Daftar Web App (`list`)

```bash
web2gtk list
```

Output:
```text
SLUG                 NAMA                   URL                                 TRAY   STEALTH 
-----------------------------------------------------------------------------------------------
claude-gtk           Claude                 https://claude.ai                   Yes    Yes     
github-gtk           GitHub                 https://github.com                  Yes    Yes     
```

### 3. Informasi Detail App (`info`)

```bash
web2gtk info claude-gtk
```

### 4. Menjalankan App Langsung (`run`)

```bash
web2gtk run claude-gtk
```
*(Atau langsung panggil command slug-nya: `claude-gtk`)*

### 5. Menghapus Web App (`remove` / `uninstall`)

```bash
# Hapus app dari menu GNOME, launcher, dan icon
web2gtk remove claude-gtk

# Hapus app beserta data cookie dan session storage-nya
web2gtk remove claude-gtk --purge
```

---

## Shortcut Keyboard

| Shortcut | Aksi |
|---|---|
| `Alt + Panah Kiri` | Kembali ke halaman sebelumnya |
| `Alt + Panah Kanan` | Maju ke halaman berikutnya |
| `Ctrl + R` | Muat ulang (Reload) |
| `Ctrl + +` / `Ctrl + -` | Zoom in / Zoom out |
| `Ctrl + 0` | Reset level zoom |
| `Ctrl + W` | Sembunyikan ke System Tray (atau tutup) |
| `Ctrl + Q` | Keluar aplikasi sepenuhnya |
| `F11` | Mode Layar Penuh (Fullscreen) |
| `F12` | Buka Web Inspector / Developer Tools |

---

## Lisensi

[MIT License](LICENSE) © 2026 Galyarder (Muhamad Galih Saputra)
