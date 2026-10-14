"""Tabla de secretos y disparador de avisos."""

import csv
from dataclasses import dataclass
from pathlib import Path

from .estado import OCULTO_1UP, USADO, Estado

TABLA = Path(__file__).with_name("secretos.csv")
CAMPOS = ["mundo", "nivel", "area", "x_desde", "x_hasta", "bloque_y", "condicion", "mensaje"]
ANTICIPO = 256  # px: una pantalla; el aviso empieza cuando el secreto está por aparecer


@dataclass(frozen=True)
class Secreto:
    mundo: int  # desde 0, como en la RAM; en el CSV va desde 1
    nivel: int
    area: int
    x_desde: int
    x_hasta: int
    bloque_y: int | None  # y del bloque que guarda el secreto: si ya se golpeó, se calla
    condicion: str
    mensaje: str

    @property
    def lugar(self):
        """Variantes del mismo secreto (chico/grande) cuentan como un solo aviso."""
        return self.mundo, self.nivel, self.area, self.x_desde


CONDICIONES = {
    "": lambda e, s: True,
    "chico": lambda e, s: e.powerup == 0,
    "grande": lambda e, s: e.powerup > 0,
    # el 1-UP oculto aparece una vez por partida: se pierde si mueres después de que se dibujó
    "1up": lambda e, s: e.flag_1up or e.bloque(s.x_desde, s.bloque_y) == OCULTO_1UP,
}


def cargar(ruta=TABLA) -> list[Secreto]:
    with open(ruta, newline="", encoding="utf-8") as f:
        tabla = [
            Secreto(
                int(r["mundo"]) - 1,
                int(r["nivel"]) - 1,
                int(r["area"], 16),
                int(r["x_desde"]),
                int(r["x_hasta"]),
                int(r["bloque_y"]) if r["bloque_y"] else None,
                r["condicion"],
                r["mensaje"],
            )
            for r in csv.DictReader(f)
        ]
    if malas := {s.condicion for s in tabla} - CONDICIONES.keys():
        raise ValueError(f"{ruta}: condición desconocida {malas}; valen {sorted(CONDICIONES)}")
    return tabla


def golpeado(e: Estado):
    """(x, y) del bloque ya golpeado más cercano sobre la cabeza de Mario, si hay."""
    x = (e.x + 8) // 16 * 16
    for fila in range((e.y + 16 - 32) // 16, -1, -1):
        if e.bloque(x, 32 + 16 * fila) == USADO:
            return x, 32 + 16 * fila
    return None


def anotar(e: Estado, nota, ruta=TABLA) -> dict:
    """Agrega a la tabla la posición de Mario, o la del bloque que acaba de golpear."""
    x, y = golpeado(e) or (e.x, None)
    fila = [e.mundo + 1, e.nivel + 1, f"{e.area:#04x}", x, x + 15, y or "", "", nota]
    with open(ruta, "a+", newline="", encoding="utf-8") as f:
        f.seek(0)
        if (previo := f.read()) and not previo.endswith("\n"):  # editado a mano sin salto final
            f.write("\n")
        csv.writer(f).writerow(fila)
    return dict(zip(CAMPOS, fila))


def tomado(e: Estado, s: Secreto) -> bool:
    return s.bloque_y is not None and e.bloque(s.x_desde, s.bloque_y) == USADO


def avisos(e: Estado, tabla, ya_dichos) -> list[Secreto]:
    """Secretos que toca anunciar ahora, del más cercano al más lejano."""
    if not e.jugando:
        return []
    return sorted(
        (
            s
            for s in tabla
            if (s.mundo, s.nivel, s.area) == (e.mundo, e.nivel, e.area)
            and s.x_desde - ANTICIPO <= e.x <= s.x_hasta
            and s.lugar not in ya_dichos
            and CONDICIONES[s.condicion](e, s)
            and not tomado(e, s)
        ),
        key=lambda s: s.x_desde,
    )


def siguiente(e: Estado, tabla, ya_dichos: set, voz_libre=True) -> str | None:
    """Próximo mensaje a decir. Al morir vacía ya_dichos para volver a avisar.

    Con la voz ocupada no saca nada: lo pendiente se vuelve a evaluar después, así
    se descarta solo si el jugador ya pasó el punto o tomó el secreto.
    """
    if not e.vivo:
        ya_dichos.clear()
    elif voz_libre and (pendientes := avisos(e, tabla, ya_dichos)):
        ya_dichos.add(pendientes[0].lugar)
        return pendientes[0].mensaje
    return None
