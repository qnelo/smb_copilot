from copiloto.avisos import ANTICIPO, CAMPOS, Secreto, anotar, cargar, siguiente
from copiloto.estado import OCULTO_1UP, USADO, estado

# secreto en un bloque del 1-1 (área 0x25), como el 1-UP oculto: x 1024..1039, y 128
BLOQUE = Secreto(0, 0, 0x25, 1024, 1039, 128, "", "bloque")
TUBO = Secreto(0, 0, 0x25, 912, 943, None, "", "tubería")
UNO_UP = Secreto(0, 0, 0x25, 1024, 1039, 128, "1up", "vida")
CERCA = BLOQUE.x_desde - ANTICIPO  # primera x en que toca avisar el bloque
VARIANTES = [Secreto(0, 0, 0x25, 336, 351, 144, "chico", "hongo"), Secreto(0, 0, 0x25, 336, 351, 144, "grande", "flor")]


def ram(x=40, area=0x25, mundo=0, nivel=0, motor=8, oper=1, caida=1, power=0, flag_1up=0, bloques=()):
    """RAM falsa con Mario en x. bloques: [(x, y, metatile)] ya dibujados."""
    r = bytearray(0x800)
    r[0x0E], r[0x770], r[0xB5], r[0x756], r[0x75D] = motor, oper, caida, power, flag_1up
    r[0x75F], r[0x75C], r[0x74E], r[0x74F] = mundo, nivel, area >> 5, area & 0x1F
    r[0x6D], r[0x86], r[0xCE] = x // 256, x % 256, 176
    dibujado = x // 16 + 16  # el juego dibuja un poco más allá del borde derecho de la pantalla
    r[0x725], r[0x726] = dibujado // 16, dibujado % 16
    for bx, by, metatile in bloques:
        col = bx // 16
        r[0x500 + col // 16 % 2 * 208 + (by - 32) // 16 * 16 + col % 16] = metatile
    return r


def recorrido(tabla, rams, ya_dichos=None, voz_libre=True):
    ya_dichos = set() if ya_dichos is None else ya_dichos
    return [siguiente(estado(r), tabla, ya_dichos, voz_libre) for r in rams]


def test_estado_x_sin_desborde_y_area():
    e = estado(ram(x=3 * 256 + 200, area=0x42, mundo=0, nivel=1))
    assert (e.x, e.area, e.mundo, e.nivel, e.vivo, e.jugando) == (968, 0x42, 0, 1, True, True)


def test_estado_muerte_y_demo_del_titulo():
    assert not estado(ram(motor=0x0B)).vivo
    assert not estado(ram(caida=2)).vivo  # cayó a un hoyo
    assert not estado(ram(oper=0)).jugando  # la demo del título también tiene motor 8


def test_estado_lee_bloque_dibujado():
    e = estado(ram(x=900, bloques=[(1024, 128, OCULTO_1UP)]))
    assert e.bloque(1030, 128) == OCULTO_1UP
    assert e.bloque(1024 + 512, 128) is None  # todavía no se dibuja


def test_avisa_con_anticipacion():
    lejos, cerca = BLOQUE.x_desde - ANTICIPO - 1, BLOQUE.x_desde - ANTICIPO
    assert recorrido([BLOQUE], [ram(x=lejos), ram(x=cerca)]) == [None, "bloque"]


def test_avisa_una_sola_vez():
    xs = (CERCA, CERCA + 50, CERCA + 100, 1000, 1030)
    assert recorrido([BLOQUE], [ram(x=x) for x in xs]) == ["bloque", None, None, None, None]


def test_variantes_del_mismo_secreto_cuentan_como_una():
    assert recorrido(VARIANTES, [ram(x=100), ram(x=100, power=1)]) == ["hongo", None]
    assert recorrido(VARIANTES, [ram(x=100, power=1)]) == ["flor"]


def test_vuelve_a_avisar_despues_de_morir():
    rams = [ram(x=CERCA), ram(x=CERCA + 50, motor=0x0B), ram(x=0, motor=0), ram(x=40), ram(x=CERCA)]
    assert recorrido([BLOQUE], rams) == ["bloque", None, None, None, "bloque"]


def test_silencio_si_el_bloque_ya_se_golpeo():
    assert recorrido([BLOQUE], [ram(x=900, bloques=[(1024, 128, USADO)])]) == [None]


def test_cambio_de_area():
    # en el cuarto de monedas (0x42) la misma x no es el mismo lugar
    assert recorrido([TUBO, BLOQUE], [ram(x=900, area=0x42)]) == [None]
    # al volver al área principal más adelante, lo que quedó atrás no se avisa
    assert recorrido([TUBO, BLOQUE], [ram(x=900, area=0x42), ram(x=1100)]) == [None, None]


def test_voz_ocupada_deja_pendiente_y_descarta_si_ya_paso():
    ya_dichos = set()
    assert recorrido([TUBO, BLOQUE], [ram(x=CERCA)], ya_dichos) == ["tubería"]
    assert recorrido([TUBO, BLOQUE], [ram(x=CERCA + 10)], ya_dichos, voz_libre=False) == [None]
    assert recorrido([TUBO, BLOQUE], [ram(x=CERCA + 20)], ya_dichos) == ["bloque"]
    ya_dichos = set()
    assert recorrido([BLOQUE], [ram(x=CERCA), ram(x=1050)], ya_dichos, voz_libre=False) == [None, None]
    assert recorrido([BLOQUE], [ram(x=1050)], ya_dichos) == [None]  # ya pasó el punto


def test_1up_oculto_solo_si_puede_aparecer():
    assert recorrido([UNO_UP], [ram(x=CERCA, flag_1up=1)]) == ["vida"]
    assert recorrido([UNO_UP], [ram(x=900, bloques=[(1024, 128, OCULTO_1UP)])]) == ["vida"]
    assert recorrido([UNO_UP], [ram(x=CERCA), ram(x=900)]) == [None, None]  # murió después de que se dibujó


def test_grabadora_anota_el_bloque_golpeado_y_la_tabla_lo_carga(tmp_path):
    tabla = tmp_path / "secretos.csv"
    tabla.write_text(",".join(CAMPOS))  # sin salto final, como lo deja algún editor
    anotar(estado(ram(x=330, bloques=[(336, 144, USADO)])), "hongo, ojo", tabla)
    anotar(estado(ram(x=600, area=0x42)), "tubería", tabla)
    golpe, tubo = cargar(tabla)
    assert (golpe.x_desde, golpe.x_hasta, golpe.bloque_y, golpe.mensaje) == (336, 351, 144, "hongo, ojo")
    assert (tubo.area, tubo.x_desde, tubo.bloque_y) == (0x42, 600, None)


def test_tabla_real_carga():
    tabla = cargar()
    assert {(s.mundo, s.nivel) for s in tabla} == {(0, 0), (0, 1)}
    assert all(s.x_desde <= s.x_hasta for s in tabla)
