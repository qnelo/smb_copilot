"""Copiloto por voz para Super Mario Bros.

    python -m copiloto           juega con el copiloto
    python -m copiloto grabar    Enter en la terminal agrega la posición actual a la tabla
    python -m copiloto doctor    revisa RetroArch, el core, la ROM y la voz
"""

import sys
import time

from . import avisos
from .estado import estado
from .retroarch import FLATPAK, RetroArch, buscar_core, buscar_retroarch, rom

INSTALAR = {
    "linux": f"flatpak install flathub {FLATPAK}",
    "darwin": "brew install --cask retroarch",
    "win32": "winget install Libretro.RetroArch   (o el instalador de https://www.retroarch.com)",
}
INSTALAR_CORE = "Abre RetroArch > Online Updater > Core Downloader > Nintendo - NES / Famicom (FCEUmm)."
SIN_VENTANA = 'video_driver = "null"\ninput_driver = "null"\naudio_driver = "null"\nconfig_save_on_exit = "false"\n'


def requisitos():
    cmd = buscar_retroarch()
    if not cmd:
        raise SystemExit(f"No encontré RetroArch. Instálalo con: {INSTALAR.get(sys.platform)}")
    core = buscar_core(cmd)
    if not core:
        raise SystemExit(f"No encontré el core FCEUmm. {INSTALAR_CORE}")
    return cmd, core, rom()


def jugar():
    cmd, core, ruta = requisitos()
    from .voz import Voz

    tabla = avisos.cargar()
    voz = Voz()
    for s in tabla:  # se generan antes de jugar: al avisar no hay latencia
        voz.wav(s.mensaje)
    ya_dichos = set()
    with RetroArch(cmd, core, ruta) as ra:
        while ra.abierto():
            if ram := ra.leer():
                if mensaje := avisos.siguiente(estado(ram), tabla, ya_dichos, voz.libre()):
                    print(mensaje)
                    voz.decir(mensaje)
                    ra.mostrar(mensaje)
            time.sleep(0.02)  # cada lectura tarda un cuadro: ~27 lecturas por segundo


def grabar():
    cmd, core, ruta = requisitos()
    print(f"Juega. Frente a un secreto (o justo después de golpear su bloque) escribe una nota y aprieta Enter.\n"
          f"Se agrega a {avisos.TABLA}. Ctrl+C para terminar.")
    with RetroArch(cmd, core, ruta) as ra:
        while ra.abierto():
            try:
                nota = input("nota> ")
            except (EOFError, KeyboardInterrupt):
                break
            ram = ra.leer()
            e = estado(ram) if ram else None
            if not e or not e.jugando:
                print("Mario no está en juego: no se grabó nada.")
                continue
            print("grabado:", avisos.anotar(e, nota))


def doctor():
    fallas = []

    def revisar(ok, bien, mal):
        print(("ok  " if ok else "MAL ") + (bien if ok else mal))
        if not ok:
            fallas.append(mal)

    cmd = buscar_retroarch()
    revisar(cmd, f"RetroArch: {' '.join(cmd or [])}", f"Falta RetroArch. Instálalo con: {INSTALAR.get(sys.platform)}")
    core = cmd and buscar_core(cmd)
    revisar(core, f"Core: {core}", f"Falta el core FCEUmm. {INSTALAR_CORE}")
    try:
        ruta = rom()
        revisar(True, f"ROM: {ruta}", "")
    except SystemExit as e:
        ruta = None
        revisar(False, "", f"{e} Ejemplo en copiloto.toml: rom = \"~/juegos/smb1.nes\"")
    try:
        import kokoro_onnx  # noqa: F401

        from .voz import ESTILOS, MODELO, reproductor

        revisar(True, "Kokoro instalado", "")
        revisar(MODELO.exists() and ESTILOS.exists(), f"Voz: {MODELO.parent}",
                "Falta la voz Kokoro: se descarga sola en el primer `make run` (~350 MB).")
        revisar(reproductor() is not None, "Reproductor de audio", "Falta un reproductor: instala pipewire, pulseaudio-utils o alsa-utils.")
    except ImportError:
        revisar(False, "", "Falta Kokoro: corre `uv sync`.")
    if cmd and core and ruta:
        # prueba real sin ventana: también confirma que el UDP a localhost cruza el sandbox de Flatpak
        with RetroArch(cmd, core, ruta, extra=SIN_VENTANA) as ra:
            for _ in range(15):
                if ram := ra.leer():
                    break
                time.sleep(0.25)
        revisar(ram, f"RetroArch entrega la RAM por UDP ({ra.leer_cmd})",
                "RetroArch no entregó la RAM por UDP en 10 s: mira .cache/retroarch.log y que nada más use el puerto 55355.")
    print("\nTodo listo: make run" if not fallas else f"\n{len(fallas)} cosa(s) por arreglar.")
    return 1 if fallas else 0


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else "jugar"
    acciones = {"jugar": jugar, "grabar": grabar, "doctor": doctor}
    if orden not in acciones:
        raise SystemExit(__doc__)
    try:
        sys.exit(acciones[orden]())
    except KeyboardInterrupt:  # RetroArch ya se cerró en el with
        pass


if __name__ == "__main__":
    main()
