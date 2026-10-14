# Copiloto por voz para Super Mario Bros.

Abre Super Mario Bros. (NES, 1985) en RetroArch y, mientras juegas, te dice por voz los secretos del
tramo que tienes adelante: bloques invisibles, 1-UP, hongos y estrellas en bloques, tuberías a cuartos
de monedas y la zona warp. Avisa una pantalla antes (`ANTICIPO` en [copiloto/avisos.py](copiloto/avisos.py)), una sola vez por vida, y se calla si ya
tomaste el secreto.

No mira la pantalla: lee la RAM de la consola emulada por los comandos de red de RetroArch y compara
la posición de Mario con una tabla. SMB es determinista, así que cada secreto está siempre en el mismo
lugar.

Probado en Linux (Pop!_OS 24.04, RetroArch 1.22.2 por Flatpak, core FCEUmm). En macOS y Windows está
documentado pero no probado.

## Instalación

1. **uv** ([instrucciones](https://docs.astral.sh/uv/getting-started/installation/)): instala Python y las
   dependencias del proyecto (Kokoro para la voz).
2. **RetroArch**:
   - Linux: `flatpak install flathub org.libretro.RetroArch`
   - macOS: `brew install --cask retroarch`
   - Windows: `winget install Libretro.RetroArch`, o el instalador de [retroarch.com](https://www.retroarch.com)
3. **Core FCEUmm**: abre RetroArch y entra a *Online Updater > Core Downloader > Nintendo - NES / Famicom (FCEUmm)*.
4. **La ROM** no viene con el proyecto: la pones tú. Crea `copiloto.toml` en la raíz del proyecto:

   ```toml
   rom = "~/juegos/smb1.nes"
   ```

   o define la variable `COPILOTO_ROM`. Si RetroArch o el core están en un lugar raro, `retroarch = "..."` y
   `core = "..."` (o `COPILOTO_RETROARCH` / `COPILOTO_CORE`) los fijan a mano. Con el RetroArch de Flatpak,
   la ROM y el proyecto tienen que estar bajo tu `$HOME`: el sandbox no ve el `/tmp` del sistema.
5. Revisa que todo esté:

   ```sh
   make doctor          # o: uv run copiloto doctor
   ```

   El doctor también abre RetroArch sin ventana y lee la RAM por UDP, así confirma que el puerto cruza
   el sandbox de Flatpak.

## Jugar

```sh
make run                 # o: uv run copiloto   (en Windows no hay make)
```

La primera vez descarga el modelo de voz [Kokoro](https://github.com/thewh1teagle/kokoro-onnx)
(~350 MB) y genera los audios. Después funciona sin conexión. Al cerrar RetroArch se cierra el
copiloto, y Ctrl+C en la terminal cierra los dos.

Cada aviso también aparece 3 s como texto arriba de la pantalla, bajo el marcador del juego. La posición,
el tamaño y el color están en el `--appendconfig` que arma [copiloto/retroarch.py](copiloto/retroarch.py).
Por eso los avisos de RetroArch salen en texto simple (sin widgets) mientras juegas con el copiloto.

La voz imita a Mario: un italiano de voz aguda que habla español. Se ajusta en
[copiloto/voz.py](copiloto/voz.py):

| Ajuste | Valor | Qué hace |
|---|---|---|
| `VOZ` | 65 % `im_nicola` + 35 % `if_sara` | Mezcla una voz italiana de hombre con una de mujer, que sube el tono sin sonar a ardilla |
| `IDIOMA` | `"it"` | Un fonetizador italiano lee el texto en español: de ahí el acento ("ladril-los", "estrel-la") |
| `TONO` | `1.45` | Más agudo. Sobre 1.5 empieza a sonar a ardilla |
| `VELOCIDAD` | `1.15` | Más rápido. Súbela si los avisos se pisan con el juego |

Para una voz neutra en español usa `VOZ = {"em_alex": 1}`, `IDIOMA = "es"` y `TONO = 1`. Las frases se
regeneran solas cuando cambias un ajuste.

## Controles

RetroArch maneja teclado y mandos. Teclado por defecto:

| NES | Tecla |
|---|---|
| Cruceta | Flechas |
| A (saltar) | X |
| B (correr, fuego) | Z |
| Start | Enter |
| Select | Shift derecho |
| Menú de RetroArch | F1 |

**Mando USB**: si RetroArch tiene su perfil, lo configura solo al conectarlo. Si no, actualiza los
perfiles en *Online Updater > Update Controller Profiles*, o asígnalo a mano: F1 > *Settings > Input >
RetroPad Binds > Port 1 Controls > Set All Controls*. Para cambiar teclas haz lo mismo.

El copiloto usa una configuración de RetroArch propia (`.cache/retroarch.cfg`), separada de la de tu
RetroArch normal. Los cambios se guardan ahí al salir. Es a propósito: RetroArch guarda en su
configuración lo que recibe por `--appendconfig`, y así el puerto de comandos no queda abierto cuando
usas RetroArch sin el copiloto.

## Agregar secretos

La tabla es [copiloto/secretos.csv](copiloto/secretos.csv). Cada fila es un aviso:

| Columna | Qué es |
|---|---|
| `mundo`, `nivel` | Como los muestra el juego: el 1-2 es `1,2` |
| `area` | Área en hexadecimal. Cambia al bajar por una tubería: el cuarto de monedas no es el nivel principal |
| `x_desde`, `x_hasta` | Dónde está el secreto, en píxeles desde el inicio del área (un bloque mide 16) |
| `bloque_y` | Opcional: y del bloque que guarda el secreto. Si el bloque ya se golpeó, no se avisa |
| `condicion` | Opcional: `chico`, `grande` o `1up` (el 1-UP oculto, que aparece una vez por partida) |
| `mensaje` | Lo que dice la voz. Que dure menos de 3 s: unas 8 palabras |

Las filas con el mismo `mundo`, `nivel`, `area` y `x_desde` son variantes de un mismo secreto: se dice
solo una. Por ejemplo, `chico` dice "hongo" y `grande` dice "flor".

Para medir las coordenadas usa la grabadora:

```sh
make grabar              # o: uv run copiloto grabar
```

Juega hasta el secreto. Si está en un bloque, golpéalo primero. Después escribe una nota en la terminal
y aprieta Enter: la grabadora agrega una fila con el mundo, el nivel, el área y la x de Mario. Si sobre
su cabeza hay un bloque recién golpeado, usa la x y la y de ese bloque. Luego edita la fila: ajusta
`x_hasta`, pon la condición y escribe el mensaje final.

## Cómo funciona

RetroArch se lanza con `network_cmd_enable` en el puerto UDP 55355. El copiloto pide
`READ_CORE_MEMORY 0 1024` y `READ_CORE_MEMORY 400 1024` unas 27 veces por segundo. RetroArch responde
a lo más 1024 bytes por pedido y atiende la red una vez por cuadro, por eso son dos pedidos juntos. Si el
core no publica su mapa de memoria, pasa a `READ_CORE_RAM`.

| Dirección | Uso |
|---|---|
| `0x6D`, `0x86` | x de Mario: `0x6D * 256 + 0x86` |
| `0x75F`, `0x75C` | Mundo y nivel, desde 0 |
| `0x74E`, `0x74F` | Tipo e índice del área actual. `0x750` no sirve: guarda el destino de la próxima tubería |
| `0x0E` | 8 = Mario tiene el control; 0x06 y 0x0B = muriendo |
| `0x770` | 1 = partida en curso. La demo del título también mueve a Mario, con 0 |
| `0xB5` | Mayor que 1: cayó a un hoyo |
| `0x756` | Power-up, 0 = chico |
| `0x75A` | Vidas, menos una (verificado: 2 → 1 → 0 → 255 en el game over) |
| `0x75D` | Se puede dibujar el 1-UP oculto. Se borra en cuanto el bloque se dibuja |
| `0x500`–`0x69F` | Bloques: dos páginas de 13 filas × 16 columnas. `0xC4` = bloque ya golpeado |
| `0x725`, `0x726` | Próxima columna que el juego va a dibujar. El buffer guarda las 32 anteriores |

Las x de la tabla se midieron en el juego: un bot recorrió el 1-1 y el 1-2 por el RetroPad de red
y registró el buffer de bloques columna por columna.

**Ojo**: mientras juegas, RetroArch escucha comandos en el UDP 55355 de todas las interfaces de red.
Cualquiera en tu red local podría mandarle comandos. Si te preocupa, bloquea ese puerto en el firewall.

## Tests

```sh
make test                # o: uv run pytest
```
