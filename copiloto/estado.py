"""Estado del juego leído de los 2 KB de RAM de la NES (0x000-0x7FF)."""

from dataclasses import dataclass

USADO = 0xC4  # metatile de bloque ya golpeado
OCULTO_1UP = 0x60  # metatile del bloque invisible con 1-UP


@dataclass(frozen=True)
class Estado:
    mundo: int  # desde 0: el 1-2 es mundo 0, nivel 1
    nivel: int
    area: int  # tipo de área (0x74E) y su índice (0x74F); cambia al bajar por una tubería
    x: int  # x de Mario en el área, en píxeles
    y: int  # y de Mario en pantalla
    powerup: int  # 0 = chico
    vidas: int  # las que muestra el juego, menos una
    vivo: bool
    jugando: bool  # partida en curso y Mario con el control (no título, demo ni transición)
    flag_1up: bool  # el 1-UP oculto de este nivel todavía puede aparecer
    bloques: bytes  # 0x500-0x69F: dos páginas de 13 filas × 16 columnas
    dibujado: int  # próxima columna de 16 px que el juego va a dibujar

    def bloque(self, x, y):
        """Metatile en (x, y) del área, o None si esa columna no está en el buffer."""
        col = x // 16
        if not self.dibujado - 32 <= col < self.dibujado:
            return None  # el buffer guarda solo las últimas 32 columnas dibujadas
        return self.bloques[col // 16 % 2 * 208 + (y - 32) // 16 * 16 + col % 16]


def estado(ram) -> Estado:
    motor = ram[0x0E]  # 8 = Mario tiene el control; 0x06 y 0x0B = muriendo
    return Estado(
        mundo=ram[0x75F],
        nivel=ram[0x75C],
        area=ram[0x74E] << 5 | ram[0x74F],  # 0x750 no sirve: guarda el destino de la próxima tubería
        x=ram[0x6D] * 256 + ram[0x86],
        y=ram[0xCE],
        powerup=ram[0x756],
        vidas=ram[0x75A],
        vivo=motor not in (0x06, 0x0B) and ram[0xB5] <= 1,  # 0xB5 > 1: cayó a un hoyo
        jugando=ram[0x770] == 1 and motor == 8,  # 0x770 = 0 también en la demo del título
        flag_1up=ram[0x75D] != 0,
        bloques=bytes(ram[0x500:0x6A0]),
        dibujado=ram[0x725] * 16 + ram[0x726],
    )
