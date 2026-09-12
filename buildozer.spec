[app]

# Nombre y paquete
title = PirataDownloader
package.name = piratadownloader
package.domain = org.piratadownloader

# Archivos fuente (este directorio contiene main.py, downloader_core.py e icon.png)
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 3.0

# yt-dlp es Python puro: funciona en Android.
# NO incluir FFmpeg (no hay receta estable); la app ya lo contempla.
requirements = python3,kivy==2.3.1,yt-dlp,mutagen,certifi,websockets,pycryptodomex

# Icono pirata
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png

orientation = portrait
fullscreen = 0

# Permisos
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# Versiones del SDK/NDK (NDK con versión completa y exacta)
android.api = 34
android.minapi = 24
android.ndk = 25.2.9519653

# Arquitecturas (arm64 cubre casi todos los móviles actuales)
android.archs = arm64-v8a,armeabi-v7a

# Aceptar licencias del SDK automáticamente
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
