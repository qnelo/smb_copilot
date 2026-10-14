"""Configuración, búsqueda y lanzamiento de RetroArch, y lectura de la RAM por UDP."""

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / ".cache"  # bajo $HOME: el RetroArch de Flatpak no ve el /tmp del sistema
FLATPAK = "org.libretro.RetroArch"
DESTINO = ("127.0.0.1", 55355)
CORES = ("fceumm", "mesen")
EXT = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
SHA1_SMB = "ea343f4e445a9050d4b4fbac2c77d0693b1d0922"  # Super Mario Bros. (World), con cabecera iNES
RUTAS = {
    "darwin": ["/Applications/RetroArch.app/Contents/MacOS/RetroArch"],
    "win32": [
        r"C:\RetroArch-Win64\retroarch.exe",
        os.path.expandvars(r"%APPDATA%\RetroArch\retroarch.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\RetroArch\retroarch.exe"),
        r"C:\Program Files (x86)\Steam\steamapps\common\RetroArch\retroarch.exe",
    ],
}


def config(clave):
    """Valor de la variable COPILOTO_<CLAVE> o de la clave en copiloto.toml."""
    if valor := os.environ.get(f"COPILOTO_{clave.upper()}"):
        return valor
    archivo = RAIZ / "copiloto.toml"
    if archivo.exists():
        with open(archivo, "rb") as f:
            return tomllib.load(f).get(clave)
    return None


def rom() -> Path:
    """Ruta de la ROM. Sale con un mensaje si falta o no es una ROM de NES."""
    valor = config("rom")
    if not valor:
        raise SystemExit('Falta la ROM: define COPILOTO_ROM o rom = "..." en copiloto.toml.')
    ruta = Path(valor).expanduser()
    if not ruta.is_file():
        raise SystemExit(f"No existe la ROM: {ruta}")
    datos = ruta.read_bytes()
    if datos[:4] != b"NES\x1a":
        raise SystemExit(f"{ruta} no es una ROM de NES: le falta la cabecera iNES.")
    if hashlib.sha1(datos).hexdigest() != SHA1_SMB:
        print("Aviso: la ROM no es la versión conocida de SMB; las direcciones de RAM podrían no calzar.")
    return ruta


def buscar_retroarch() -> list[str] | None:
    """Comando que lanza RetroArch, o None."""
    if valor := config("retroarch"):
        return [str(Path(valor).expanduser())]
    if ruta := shutil.which("retroarch"):
        return [ruta]
    if shutil.which("flatpak") and subprocess.run(["flatpak", "info", FLATPAK], capture_output=True).returncode == 0:
        return ["flatpak", "run", FLATPAK]
    return next(([r] for r in RUTAS.get(sys.platform, []) if Path(r).is_file()), None)


def buscar_core(cmd) -> Path | None:
    if valor := config("core"):
        return Path(valor).expanduser()
    casa = Path.home()
    carpetas = [
        casa / ".var/app" / FLATPAK / "config/retroarch/cores",  # primero: Flatpak no ve /usr/lib del sistema
        casa / ".config/retroarch/cores",
        Path("/usr/lib/x86_64-linux-gnu/libretro"),
        Path("/usr/lib/aarch64-linux-gnu/libretro"),
        Path("/usr/lib/libretro"),
        Path("/usr/lib64/libretro"),
        casa / "Library/Application Support/RetroArch/cores",
        Path(cmd[-1]).parent / "cores",  # Windows: junto al .exe
        Path(os.environ.get("APPDATA", casa)) / "RetroArch/cores",
    ]
    rutas = (c / f"{n}_libretro{EXT}" for n in CORES for c in carpetas)
    return next((r for r in rutas if r.is_file()), None)


class RetroArch:
    """RetroArch abierto con la ROM y los comandos de red activos."""

    def __init__(self, cmd, core, rom, extra=""):
        CACHE.mkdir(exist_ok=True)
        extra_cfg = CACHE / "copiloto.cfg"
        extra_cfg.write_text(
            f'network_cmd_enable = "true"\nnetwork_cmd_port = "{DESTINO[1]}"\n'
            # avisos arriba, bajo el marcador: los de widgets salen abajo a la izquierda y tapan a Mario
            'menu_enable_widgets = "false"\nvideo_message_pos_x = "0.05"\nvideo_message_pos_y = "0.78"\n'
            'video_font_size = "24"\nvideo_message_color = "ffffff"\n'
            'video_msg_bgcolor_enable = "true"\nvideo_msg_bgcolor_opacity = "0.7"\n'
            f"{extra}"
        )
        # config propia: al salir RetroArch guarda en su config lo del --appendconfig, y no
        # queremos dejar el puerto de comandos abierto en el RetroArch normal del usuario.
        # Tiene que existir: si falta, RetroArch ignora el --appendconfig.
        (CACHE / "retroarch.cfg").touch()
        base = ["--config", str(CACHE / "retroarch.cfg"), "--appendconfig", str(extra_cfg)]
        log = open(CACHE / "retroarch.log", "w")
        self.proc = subprocess.Popen([*cmd, *base, "-L", str(core), str(rom)], stdout=log, stderr=subprocess.STDOUT)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.leer_cmd = "READ_CORE_MEMORY"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()

    def abierto(self):
        return self.proc.poll() is None

    def leer(self) -> bytes | None:
        """Los 2 KB de RAM, o None si RetroArch todavía no responde."""
        self.s.setblocking(False)
        try:
            while True:  # descarta respuestas atrasadas
                self.s.recv(8192)
        except OSError:
            pass
        self.s.settimeout(0.5)
        partes = {}
        try:
            # RetroArch responde a lo más 1024 bytes y atiende la red una vez por cuadro:
            # dos pedidos juntos salen en el mismo cuadro
            for base in (0, 0x400):
                self.s.sendto(f"{self.leer_cmd} {base:x} 1024".encode(), DESTINO)
            while len(partes) < 2:
                r = self.s.recv(8192).decode().split()
                if r[:1] != [self.leer_cmd]:
                    continue
                if r[2] == "-1":
                    if "map" in r:  # core sin mapa de memoria: usar las direcciones de RetroAchievements
                        self.leer_cmd = "READ_CORE_RAM"
                    return None
                partes[int(r[1], 16)] = bytes.fromhex("".join(r[2:]))
        except OSError:  # timeout, o en Windows el ICMP de puerto cerrado mientras arranca
            return None
        ram = partes[0] + partes[0x400]
        return ram if len(ram) == 0x800 else None

    def mostrar(self, texto):
        """Muestra el texto sobre el juego por 3 s (180 cuadros, fijo en RetroArch)."""
        self.s.sendto(f"SHOW_MSG {texto}".encode(), DESTINO)

    def cerrar(self):
        """QUIT por UDP (RetroArch pide confirmación, por eso se repite); si no, a la fuerza."""
        for _ in range(10):
            if not self.abierto():
                return
            self.s.sendto(b"QUIT", DESTINO)
            try:
                self.proc.wait(0.3)
            except subprocess.TimeoutExpired:
                pass
        self.proc.kill()
        if self.proc.args[:2] == ["flatpak", "run"]:
            # matar `flatpak run` deja vivo a RetroArch dentro del sandbox
            subprocess.run(["flatpak", "kill", FLATPAK], capture_output=True)
