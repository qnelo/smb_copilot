"""Voz del copiloto: Kokoro genera cada frase una vez (caché por hash del texto) y el
reproductor del sistema la toca encima del sonido del juego."""

import hashlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

from .retroarch import CACHE

URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODELO = CACHE / "voces" / "kokoro-v1.0.onnx"
ESTILOS = CACHE / "voces" / "voices-v1.0.bin"
# Mario: voz italiana de hombre con algo de una de mujer, que sube el tono sin sonar a ardilla
VOZ = {"im_nicola": 0.65, "if_sara": 0.35}
IDIOMA = "it"  # fonetizador italiano leyendo español: de ahí el acento ("ladril-los", "estrel-la")
VELOCIDAD = 1.15  # > 1 habla más rápido
TONO = 1.45  # > 1 más agudo: el WAV se marca a más Hz y se sintetiza más lento en igual proporción


def reproductor() -> list[str] | None:
    """Comando que reproduce un WAV, [] en Windows (winsound) o None si no hay."""
    if sys.platform == "win32":
        return []
    if sys.platform == "darwin":
        return ["afplay"]
    return next(([p] for p in ("pw-play", "paplay", "aplay") if shutil.which(p)), None)


def descargar_modelo():
    print("Descargando la voz Kokoro (~350 MB, solo la primera vez)...")
    MODELO.parent.mkdir(parents=True, exist_ok=True)
    for ruta in (MODELO, ESTILOS):
        if not ruta.exists():
            tmp = ruta.with_suffix(".parcial")  # una descarga cortada no deja un modelo roto
            urllib.request.urlretrieve(URL + ruta.name, tmp)
            tmp.replace(ruta)


class Voz:
    def __init__(self):
        self.cmd = reproductor()
        if self.cmd is None:
            raise SystemExit("No hay reproductor de audio: instala pipewire, pulseaudio-utils o alsa-utils.")
        if not (MODELO.exists() and ESTILOS.exists()):
            descargar_modelo()
        self.kokoro = None  # se carga solo si falta generar alguna frase
        self.hasta = 0.0

    def wav(self, texto) -> Path:
        clave = f"{VOZ}|{IDIOMA}|{VELOCIDAD}|{TONO}|{texto}"
        ruta = CACHE / "frases" / f"{hashlib.sha1(clave.encode()).hexdigest()[:16]}.wav"
        if not ruta.exists():
            if self.kokoro is None:
                from kokoro_onnx import Kokoro

                self.kokoro = Kokoro(str(MODELO), str(ESTILOS))
                self.estilo = sum(peso * self.kokoro.get_voice_style(v) for v, peso in VOZ.items())
            if IDIOMA == "it":
                texto = re.sub(r"qu(?=[eiéí])", "ch", texto)  # en italiano "qu" suena /kw/: "bloque" saldría "blokwe"
            audio, rate = self.kokoro.create(texto, voice=self.estilo, speed=VELOCIDAD / TONO, lang=IDIOMA)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            tmp = ruta.with_suffix(".tmp")
            with wave.open(str(tmp), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(round(rate * TONO))
                w.writeframes((audio.clip(-1, 1) * 32767).astype("int16").tobytes())
            tmp.replace(ruta)
        return ruta

    def libre(self):
        return time.monotonic() >= self.hasta

    def decir(self, texto):
        ruta = self.wav(texto)
        with wave.open(str(ruta)) as w:
            duracion = w.getnframes() / w.getframerate()
        if sys.platform == "win32":
            import winsound

            winsound.PlaySound(str(ruta), winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            subprocess.Popen([*self.cmd, str(ruta)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.hasta = time.monotonic() + duracion + 0.3  # una frase a la vez, con una pausa corta
