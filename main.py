# -*- coding: utf-8 -*-
"""
PirataDownloader para Android (Kivy)
====================================
Nota: en Android no hay FFmpeg, así que se descarga en formato
progresivo (video+audio ya unidos) o audio nativo, sin conversión.
"""

import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

from downloader_core import (CALIDADES, IDIOMAS_SUBS, MotorDescarga,
                             cargar_config, guardar_config)

ROJO = (0.90, 0.22, 0.27, 1)
AZUL = (0.11, 0.21, 0.34, 1)
FONDO = (0.04, 0.07, 0.17, 1)
TEXTO = (0.92, 0.95, 1, 1)


def carpeta_descargas():
    """Carpeta de descargas visible para el usuario en Android."""
    ext = os.environ.get('EXTERNAL_STORAGE')
    ruta = os.path.join(ext, 'Download', 'PirataDownloader') if ext else os.getcwd()
    os.makedirs(ruta, exist_ok=True)
    return ruta


def pedir_permisos():
    try:
        from android.permissions import Permission, request_permissions
        request_permissions([Permission.WRITE_EXTERNAL_STORAGE,
                             Permission.READ_EXTERNAL_STORAGE])
    except Exception:
        pass  # No estamos en Android o no hace falta


class PirataAndroid(App):
    def build(self):
        self.title = "PirataDownloader"
        self.cfg = cargar_config()
        self.motor = None

        raiz = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))

        raiz.add_widget(Label(text="🏴‍☠️ PirataDownloader",
                              font_size='24sp', bold=True, size_hint_y=None,
                              height=dp(48), color=ROJO))

        # URL
        fila_url = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.url = TextInput(hint_text="Pega la URL del video...",
                             multiline=False, background_color=AZUL,
                             foreground_color=TEXTO)
        fila_url.add_widget(self.url)
        btn_pegar = Button(text="Pegar", size_hint_x=None, width=dp(80),
                           background_color=AZUL)
        btn_pegar.bind(on_release=self._pegar)
        fila_url.add_widget(btn_pegar)
        raiz.add_widget(fila_url)

        # Modo y calidad
        fila_opts = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.modo = Spinner(text="Video", values=("Video", "Audio"),
                            background_color=AZUL)
        fila_opts.add_widget(self.modo)
        self.calidad = Spinner(text="Full HD (1080p)",
                               values=[f"{v}" for k, v in CALIDADES.items()],
                               background_color=AZUL)
        fila_opts.add_widget(self.calidad)
        raiz.add_widget(fila_opts)

        # Subtítulos
        raiz.add_widget(Label(text="Subtítulos (códigos: es,en,fr,it...)",
                              size_hint_y=None, height=dp(24), color=TEXTO))
        self.subs = TextInput(text=self.cfg.get('subs', 'es,en'), multiline=False,
                              size_hint_y=None, height=dp(40),
                              background_color=AZUL, foreground_color=TEXTO)
        raiz.add_widget(self.subs)

        # Switch playlist
        fila_pl = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        fila_pl.add_widget(Label(text="¿Es playlist/canal completo?", color=TEXTO))
        self.sw_playlist = Switch(active=False)
        fila_pl.add_widget(self.sw_playlist)
        raiz.add_widget(fila_pl)

        # Progreso
        self.barra = ProgressBar(max=100, size_hint_y=None, height=dp(18))
        raiz.add_widget(self.barra)
        self.lbl_estado = Label(text="Listo para zarpar ⚓", size_hint_y=None,
                                height=dp(28), color=TEXTO)
        raiz.add_widget(self.lbl_estado)

        # Botón principal
        self.btn = Button(text="⬇  DESCARGAR", size_hint_y=None, height=dp(56),
                          background_color=ROJO, bold=True, font_size='18sp')
        self.btn.bind(on_release=self._descargar)
        raiz.add_widget(self.btn)

        # Registro
        self.log = Label(text="", size_hint_y=None, color=TEXTO,
                         halign='left', valign='top')
        self.log.bind(texture_size=lambda *_: setattr(
            self.log, 'height', self.log.texture_size[1]))
        scroll = ScrollView()
        scroll.add_widget(self.log)
        raiz.add_widget(scroll)

        from kivy.core.window import Window
        Window.clearcolor = FONDO

        pedir_permisos()
        self._log_ui(f"Descargas en: {carpeta_descargas()}")
        return raiz

    # ------------------------------------------------------------------
    def _log_ui(self, texto):
        def _f(dt):
            self.log.text += texto + "\n"
        Clock.schedule_once(_f)

    def _pegar(self, *_):
        try:
            self.url.text = Clipboard.paste()
        except Exception:
            self._log_ui("No se pudo leer el portapapeles.")

    def _descargar(self, *_):
        url = self.url.text.strip()
        if not url:
            self._log_ui("⚠ Pega primero una URL.")
            return

        self.cfg['subs'] = self.subs.text.strip()
        calidad_txt = self.calidad.text
        self.cfg['calidad'] = next(
            (k for k, v in CALIDADES.items() if v == calidad_txt), '1080')
        guardar_config(self.cfg)

        modo = 'audio' if self.modo.text == 'Audio' else 'video'
        es_playlist = self.sw_playlist.active

        self.motor = MotorDescarga(
            self.cfg,
            on_mensaje=lambda t, n='info': self._log_ui(t),
            on_progreso=self._progreso)
        # Carpeta de salida visible en Android
        import downloader_core
        downloader_core.CARPETA_SALIDA = carpeta_descargas()

        self.btn.disabled = True
        self.lbl_estado.text = "Descargando..."

        def trabajo():
            # simple=True: sin FFmpeg en Android -> formato progresivo
            exito, _ = self.motor.descargar(url, modo=modo,
                                            es_playlist=es_playlist, simple=True)
            Clock.schedule_once(lambda dt: self._fin(exito))

        threading.Thread(target=trabajo, daemon=True).start()

    def _progreso(self, porcentaje, velocidad, eta):
        def _f(dt):
            self.barra.value = porcentaje
            self.lbl_estado.text = f"{porcentaje:.0f}%  |  {velocidad}  |  ETA {eta}"
        Clock.schedule_once(_f)

    def _fin(self, exito):
        self.btn.disabled = False
        self.barra.value = 0
        self.lbl_estado.text = ("✅ ¡Descarga completada! 🏴‍☠️" if exito
                                else "❌ Falló la descarga. Revisa el registro.")


if __name__ == '__main__':
    PirataAndroid().run()
