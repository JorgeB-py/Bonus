# Anotador local de modismos colombianos

Sustituye Label Studio para esta tarea específica. Mismas anotaciones, atajos de teclado, imágenes cacheadas. Al final exportas dos CSVs y los envías a `ma.pinzonr1@uniandes.edu.co`.

## Instalación (una sola vez)

```powershell
pip install flask requests
```

`requests` probablemente ya lo tienes.

## Paso 1 — Pre-descargar imágenes (~10–20 min, una vez)

```powershell
cd C:\Users\jorgi\Desktop\Machine_learning_tech\modulo_2\Bonus\anotador
python download_images.py
```

Descarga ~4500 imágenes (Single + Multi GEMINI) a `images/`. Se puede interrumpir y reanudar — solo baja lo que falte. Si quedan errores se listan en `download_errors.txt`; puedes volver a correr el script para reintentar.

## Paso 2 — Arrancar el anotador

```powershell
python app.py
```

Abre <http://localhost:5000> en tu navegador. Verás la pantalla con dos progress bars y botones para continuar Single o Multi.

Las anotaciones se guardan automáticamente en `annotations.db` (SQLite). Puedes cerrar el servidor y volver — retoma justo donde te quedaste.

## Atajos de teclado

### Evaluación 1 (Single)
- `S` / `N` → Sí / No
- `M` → toggle "esta expresión NO es un modismo colombiano"
- `C` → enfocar el campo de comentarios
- `Enter` → guardar y avanzar a la siguiente tarea
- `←` / `→` → tarea anterior / siguiente (sin guardar)
- `Esc` → salir de un campo de texto

### Evaluación 2 (Multi)
- `Tab` / `Shift+Tab` → cambiar la **imagen activa** (resaltada con borde azul)
- Sobre la imagen activa:
  - `F` → Figurada
  - `L` → Literal
  - `X` → Mixta (la M está tomada por casos especiales)
  - `A` → Aleatoria
  - `1` `2` `3` `4` → asignar ranking
- `M` → toggle "no es modismo colombiano"
- `D` → toggle "es modismo pero no de doble sentido"
- `Enter` → validar (ranking sin repetir + 4 clasificaciones) y guardar
- `←` / `→` → tarea anterior / siguiente
- `Esc` → salir de un campo de texto

## Validaciones automáticas (Multi)

Al pulsar Enter, el formulario rechaza guardar si:
- Falta clasificar alguna imagen
- Falta asignar ranking
- Los rankings se repiten (deben ser 1, 2, 3, 4 únicos)

Excepción: si marcas "no es modismo" o "no es de doble sentido", se permite guardar sin clasificación/ranking (siguiendo el instructivo).

## Paso 3 — Exportar y enviar

Cuando hayas terminado (o quieras hacer un backup intermedio):
- Haz click en **"Exportar Single CSV"** y **"Exportar Multi CSV"** en la barra superior, o ve a:
  - <http://localhost:5000/export/single>
  - <http://localhost:5000/export/multi>

Los CSVs salen con los nombres:
- `SingleLabelStudioGPT_JorgeDavidBustamantePino_anotado.csv`
- `MultiLabelStudioGEMINI_JorgeDavidBustamantePino_anotado.csv`

El formato replica el de Label Studio (las elecciones se serializan como `{"choices": ["Sí"]}` y los textos como `{"text": [...]}`).

Envíalos a `ma.pinzonr1@uniandes.edu.co` con asunto:
> Anotación imágenes modismos colombianos – Jorge David Bustamante Pino

## Estructura del proyecto

```
anotador/
├── app.py                  # Flask app
├── download_images.py      # Pre-descarga imágenes
├── annotations.db          # SQLite (se crea automáticamente)
├── url_map.json            # Mapeo URL remota → archivo local
├── images/                 # Imágenes descargadas
├── static/style.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── single.html
│   └── multi.html
└── README.md
```

## Notas
- Si en algún momento quieres empezar de cero, borra `annotations.db`.
- Si modificaste un CSV de entrada y agregaste nuevas filas, reinicia la app para que las cargue.
- El servidor solo escucha en `127.0.0.1` (localhost) — no se expone a la red.
