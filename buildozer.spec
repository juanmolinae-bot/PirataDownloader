[app]

# Nombre y paquete
title = PirataDownloader
package.name = piratadownloader
package.domain = org.piratadownloader

# Archivos fuente: este directorio contiene main.py.
# downloader_core.py va JUNTO a main.py (cópialo aquí antes de compilar
# o usa source.include_exts para traerlo del directorio padre).
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 3.0

# Dependencias: yt-dlp es Python puro, funciona en Android.
# NO incluir FFmpeg (no existe receta estable); la app ya lo contempla
# descargando en formato progresivo (video+audio unidos de fábrica).
requirements = python3,kivy==2.3.0,yt-dlp,mutagen,certifi,websockets,pycryptodomex

# Icono pirata
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png

orientation = portrait
fullscreen = 0

# Permisos para guardar en Descargas
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# API moderna de Android
android.api = 34
android.minapi = 24
android.ndk = 25b

# Arquitecturas (arm64 cubre la gran mayoría de móviles actuales)
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
