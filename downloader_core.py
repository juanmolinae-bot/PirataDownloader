# -*- coding: utf-8 -*-
"""
downloader_core.py — Motor de descargas de PirataDownloader
============================================================
Núcleo reutilizable basado en yt-dlp. Lo usan la GUI de escritorio,
la interfaz de línea de comandos y la app Android.

Callbacks disponibles (todos opcionales):
    on_mensaje(texto, nivel)              nivel: 'info' | 'ok' | 'aviso' | 'error'
    on_progreso(porcentaje_0a100, velocidad, eta)
    on_fin(exito: bool, detalle: str)
"""

import json
import logging
import os
import random
import re
import time

import yt_dlp

VERSION = "3.0"
CARPETA_SALIDA = os.path.join(os.path.expanduser("~"), "Descargas", "PirataDownloader")
ARCHIVO_LOG = os.path.join(CARPETA_SALIDA, "pirata.log")
ARCHIVO_HISTORIAL = os.path.join(CARPETA_SALIDA, "historial.txt")
ARCHIVO_CONFIG = os.path.join(CARPETA_SALIDA, "config.json")

CALIDADES = {
    '2160': '4K Ultra HD (2160p)',
    '1440': '2K QHD (1440p)',
    '1080': 'Full HD (1080p)',
    '720':  'HD (720p)',
    '480':  'SD (480p)',
    'mejor': 'La mejor disponible',
}

IDIOMAS_SUBS = {
    'es': 'Español', 'en': 'Inglés', 'fr': 'Francés', 'it': 'Italiano',
    'pt': 'Portugués', 'de': 'Alemán', 'ja': 'Japonés', 'ko': 'Coreano', 'zh': 'Chino',
}

NAVEGADORES = ('chrome', 'firefox', 'edge', 'opera', 'brave', 'vivaldi', 'safari', 'chromium')

FORMATOS_AUDIO = ('mp3', 'm4a', 'opus', 'flac', 'wav')

CATEGORIAS_SPONSORBLOCK = ['sponsor', 'intro', 'outro', 'selfpromo', 'interaction', 'preview']

CONFIG_DEFECTO = {
    "calidad": "1080",
    "subs": "es,en",
    "subs_auto": True,
    "subs_incidir": True,
    "contenedor": "mp4",
    "formato_audio": "mp3",
    "sponsorblock": False,
    "dividir_capitulos": False,
    "geo_bypass": False,
    "navegador_cookies": None,
    "proxy": None,
    "limite_velocidad_mb": 0,
    "pausas_antibaneo": False,
}


class DescargaCancelada(Exception):
    """Se lanza desde el hook de progreso cuando el usuario cancela."""


def cargar_config():
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    if os.path.exists(ARCHIVO_CONFIG):
        try:
            with open(ARCHIVO_CONFIG, 'r', encoding='utf-8') as f:
                cfg = CONFIG_DEFECTO.copy()
                cfg.update(json.load(f))
                return cfg
        except (json.JSONDecodeError, OSError):
            pass
    return CONFIG_DEFECTO.copy()


def guardar_config(cfg):
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    with open(ARCHIVO_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def parsear_seccion(texto):
    """'HH:MM:SS-HH:MM:SS' -> [{'start_time': s, 'end_time': s}] o None."""
    patron = re.compile(r'^(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(\d{1,2}:\d{2}(?::\d{2})?)$')
    m = patron.match(texto.strip())
    if not m:
        return None
    def a_segundos(t):
        p = [int(x) for x in t.split(':')]
        return p[-1] + p[-2] * 60 + (p[0] * 3600 if len(p) == 3 else 0)
    return [{'start_time': a_segundos(m.group(1)), 'end_time': a_segundos(m.group(2))}]


def construir_selector_video(altura_max, contenedor='mp4', simple=False):
    """Selector de formato. 'simple' evita combinar streams (para Android sin FFmpeg)."""
    if simple:
        if altura_max:
            return f'best[height<={altura_max}]/best'
        return 'best'
    ext = 'mp4' if contenedor == 'mp4' else None
    if altura_max:
        if ext:
            return (f'bestvideo[height<={altura_max}][ext={ext}]+bestaudio[ext=m4a]/'
                    f'bestvideo[height<={altura_max}]+bestaudio/'
                    f'best[height<={altura_max}][ext={ext}]/best[height<={altura_max}]/best')
        return f'bestvideo[height<={altura_max}]+bestaudio/best[height<={altura_max}]/best'
    return (f'bestvideo[ext={ext}]+bestaudio[ext=m4a]/bestvideo+bestaudio/best' if ext
            else 'bestvideo+bestaudio/best')


def verificar_ffmpeg():
    """Devuelve la ruta de FFmpeg si está disponible, o None."""
    import shutil
    return shutil.which('ffmpeg')


class MotorDescarga:
    """Motor central: configura yt-dlp y ejecuta descargas con callbacks."""

    def __init__(self, cfg=None, on_mensaje=None, on_progreso=None):
        self.cfg = {**CONFIG_DEFECTO, **(cfg or cargar_config())}
        self.on_mensaje = on_mensaje or (lambda t, n='info': None)
        self.on_progreso = on_progreso or (lambda p, v, e: None)
        self._cancelar = False
        os.makedirs(CARPETA_SALIDA, exist_ok=True)
        logging.basicConfig(
            filename=ARCHIVO_LOG, level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s', encoding='utf-8')

    # ---------------------------------------------------------------
    def cancelar(self):
        self._cancelar = True

    # ---------------------------------------------------------------
    def _emitir(self, texto, nivel='info'):
        logging.info(texto) if nivel != 'error' else logging.error(texto)
        self.on_mensaje(texto, nivel)

    def _hook(self, d):
        if self._cancelar:
            raise DescargaCancelada()
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            descargado = d.get('downloaded_bytes', 0)
            porcentaje = (descargado / total * 100) if total else 0.0
            self.on_progreso(
                porcentaje,
                d.get('_speed_str', '...'),
                d.get('_eta_str', '...'))
        elif d['status'] == 'finished':
            self.on_progreso(100.0, '-', '-')
            self._emitir('Uniendo y procesando el archivo final...')

    # ---------------------------------------------------------------
    def _opciones_base(self):
        opts = {
            'paths': {'home': CARPETA_SALIDA},
            'outtmpl': '%(playlist_index)s - %(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [self._hook],
            'retries': 10,
            'fragment_retries': 10,
            'continuedl': True,
            'concurrent_fragment_downloads': 4,
            'writethumbnail': True,
            'embed_metadata': True,
            'embed_thumbnail': True,
            'windowsfilenames': True,
            'download_archive': ARCHIVO_HISTORIAL,
            'http_headers': {
                'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/124.0 Safari/537.36'),
            },
        }
        if self.cfg.get('navegador_cookies'):
            opts['cookiesfrombrowser'] = (self.cfg['navegador_cookies'],)
        if self.cfg.get('geo_bypass'):
            opts['geo_bypass'] = True
        if self.cfg.get('proxy'):
            opts['proxy'] = self.cfg['proxy']
        limite = self.cfg.get('limite_velocidad_mb', 0)
        if limite and float(limite) > 0:
            opts['ratelimit'] = int(float(limite) * 1024 * 1024)
        if self.cfg.get('pausas_antibaneo'):
            opts['sleep_interval'] = 3
            opts['max_sleep_interval'] = 10
            opts['sleep_interval_requests'] = 1
        return opts

    # ---------------------------------------------------------------
    def obtener_info(self, url):
        """Devuelve dict con título, miniatura, duración, nº de formatos y si es playlist."""
        opts = self._opciones_base()
        opts.update({'extract_flat': False, 'noplaylist': True})
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info is None:
            return None
        entradas = info.get('entries')
        if entradas:
            entradas = list(entradas)
            return {
                'titulo': info.get('title', 'Playlist'),
                'es_playlist': True,
                'n_videos': len(entradas),
                'miniatura': (entradas[0] or {}).get('thumbnail'),
                'duracion': None,
                'n_formatos': 0,
            }
        return {
            'titulo': info.get('title', 'Sin título'),
            'es_playlist': False,
            'n_videos': 1,
            'miniatura': info.get('thumbnail'),
            'duracion': info.get('duration'),
            'n_formatos': len(info.get('formats') or []),
            'canal': info.get('uploader') or info.get('channel'),
            'subs_disponibles': sorted(set(list((info.get('subtitles') or {}).keys()))),
        }

    # ---------------------------------------------------------------
    def listar_formatos(self, url):
        """Devuelve lista de líneas legibles con los formatos disponibles."""
        opts = self._opciones_base()
        opts.update({'noplaylist': True})
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        lineas = []
        for f in (info.get('formats') or []):
            res = f.get('resolution') or (f"{f.get('width')}x{f.get('height')}" if f.get('width') else 'audio')
            lineas.append(f"{f.get('format_id','?'):>6} | {f.get('ext','?'):<5} | "
                          f"{res:<12} | {f.get('format_note','') or ''}")
        return lineas

    # ---------------------------------------------------------------
    def descargar(self, url, modo='video', es_playlist=False,
                  rango_playlist=None, seccion=None, simple=False):
        """Descarga una URL. Devuelve (exito, mensaje)."""
        self._cancelar = False
        ydl_opts = self._opciones_base()
        ydl_opts['noplaylist'] = not es_playlist
        if rango_playlist:
            ydl_opts['playlist_items'] = rango_playlist

        if modo == 'audio':
            faudio = self.cfg.get('formato_audio', 'mp3')
            if simple:
                # Sin FFmpeg (Android): solo audio nativo sin convertir
                ydl_opts['format'] = 'bestaudio/best'
            else:
                pp = {'key': 'FFmpegExtractAudio', 'preferredcodec': faudio}
                if faudio == 'mp3':
                    pp['preferredquality'] = '320'
                ydl_opts.update({'format': 'bestaudio/best',
                                 'postprocessors': [pp, {'key': 'EmbedThumbnail'},
                                                    {'key': 'FFmpegMetadata'}]})
        else:
            contenedor = self.cfg.get('contenedor', 'mp4')
            calidad = self.cfg.get('calidad', '1080')
            altura = int(calidad) if calidad != 'mejor' else None
            ydl_opts['format'] = construir_selector_video(altura, contenedor, simple=simple)
            if not simple:
                pps = [{'key': 'FFmpegMetadata'}, {'key': 'EmbedThumbnail'}]
                if contenedor == 'mp4':
                    pps.insert(0, {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'})
                langs = [l.strip() for l in self.cfg.get('subs', '').split(',') if l.strip()]
                if langs:
                    ydl_opts.update({
                        'writesubtitles': True,
                        'writeautomaticsub': self.cfg.get('subs_auto', True),
                        'subtitleslangs': langs,
                    })
                    pps.insert(0, {'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'})
                    if self.cfg.get('subs_incidir', True):
                        pps.insert(1, {'key': 'FFmpegEmbedSubtitle'})
                if self.cfg.get('sponsorblock'):
                    ydl_opts['sponsorblock_remove'] = CATEGORIAS_SPONSORBLOCK
                if self.cfg.get('dividir_capitulos'):
                    ydl_opts['split_chapters'] = True
                else:
                    ydl_opts['embed_chapters'] = True
                if seccion:
                    ydl_opts['download_sections'] = seccion
                    ydl_opts['force_keyframes_at_cuts'] = True
                ydl_opts['merge_output_format'] = contenedor
                ydl_opts['postprocessors'] = pps

        self._emitir(f'Analizando: {url}')
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self._emitir(f'Completado: {url}', 'ok')
            return True, 'ok'
        except DescargaCancelada:
            self._emitir('Descarga cancelada por el usuario.', 'aviso')
            return False, 'cancelada'
        except yt_dlp.utils.DownloadError as e:
            msg = str(e).split('\n')[0]
            self._emitir(f'Fallo: {msg}', 'error')
            return False, msg
        except Exception as e:
            self._emitir(f'Error inesperado: {e}', 'error')
            return False, str(e)

    # ---------------------------------------------------------------
    def descargar_lote(self, urls, **kwargs):
        """Descarga una lista de URLs. Devuelve (exitosas, fallidas)."""
        exitosas, fallidas = 0, 0
        for i, url in enumerate(urls, 1):
            if self._cancelar:
                break
            self._emitir(f'--- [{i}/{len(urls)}] {url} ---')
            exito, _ = self.descargar(url, **kwargs)
            if exito:
                exitosas += 1
            else:
                fallidas += 1
            if self.cfg.get('pausas_antibaneo') and i < len(urls) and not self._cancelar:
                pausa = random.uniform(3, 10)
                self._emitir(f'Pausa anti-baneo de {pausa:.1f}s...')
                time.sleep(pausa)
        return exitosas, fallidas
