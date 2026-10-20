# Audio Normalizer · Bar-Level Rubberband Studio

Herramienta en Python para normalizar canciones analógicas o grabadas sin metrónomo a un **BPM plano constante** a **44,100 Hz**, corrigiendo fluctuaciones leves de tempo (batería humana o arrastre de cinta analógica) **sin perder el groove ni el swing interno del compás**.

---

## Características Principales

- **Cuantización a Nivel de Compás (*Bar-Level Quantization*):**
  Alinea los *downbeats* de cada compás ($4/4$, $3/4$, $6/8$) sobre una rejilla matemática *sample-exact* desde el primer pulso real ($t_0$), manteniendo intacto el micro-timing y el *swing* de los pulsos internos:
  $$\Delta t = \frac{60}{\text{BPM\_objetivo}} \times \text{beats\_per\_bar}, \quad t_k = t_0 + k \cdot \Delta t$$
- **Curva de Velocidad Continua ($\text{C}^1$) sin Cortes ni Crossfades:**
  Calcula una modulación de tempo continua mediante interpolación de coseno elevado a `50 Hz` (`882 muestras` por bloque a `44,100 Hz`) que preserva de forma exacta la integral temporal de cada compás sin saltos bruscos de fase.
- **Motor DSP Exclusivo FFmpeg Rubber Band R3:**
  Usa `librosa` únicamente para el análisis rítmico y delega el estiramiento acústico directamente al filtro nativo `rubberband` de FFmpeg con preservación de transientes y coherencia de fase:
  ```text
  aresample=44100:resampler=soxr,asetnsamples=n=882:p=0,asendcmd=f='...',rubberband=transients=crisp:detector=compound:phase=independent:pitchq=quality
  ```
- **Estándar de Exportación Compatible con Analizadores de Timing:**
  Frecuencia fija a **44,100 Hz estéreo** y codificación **MP3 a 320 kbps CBR (`libmp3lame`)** o **WAV 24-bit (`PCM_24`)**.

---

## Uso del Ejecutable Portable (Windows)

No requiere instalar Python ni FFmpeg en el sistema:

1. Descarga `AudioNormalizer-v1.0.0-win64.zip` desde la sección **Releases** de GitHub.
2. Descomprime el archivo en cualquier carpeta.
3. Ejecuta **`AudioNormalizer.exe`**.
4. Se abrirá automáticamente la interfaz web local en tu navegador (`http://127.0.0.1:7860`).

---

## Instalación y Uso desde Código Fuente

### 1. Requisitos previos
- **Python 3.11+**
- **FFmpeg** con soporte para `librubberband`, `libsoxr` y `libmp3lame` (por ejemplo, la compilación *full_build* de Gyan.dev en Windows).

### 2. Instalar dependencias

```powershell
python -m pip install -r requirements.txt
```

### 3. Lanzar la Interfaz Web (Gradio)

```powershell
python app.py
```

El servidor local buscará automáticamente un puerto libre entre `7860` y `7890` y abrirá el navegador.

### 4. Uso por Línea de Comandos (CLI)

```powershell
# Auto-detectando el BPM nominal (mediana de los compases)
python main.py cancion_original.mp3 cancion_normalizada.mp3 --beats-per-bar 4

# Forzando un BPM objetivo específico (ej. 139.0 BPM)
python main.py cancion_original.mp3 cancion_normalizada.mp3 --beats-per-bar 4 --bpm 139.0
```

---

## Compilar el Ejecutable Portable (`.exe`)

Para generar nuevamente el paquete distribuible en `dist/AudioNormalizer/`:

```powershell
python -m PyInstaller --noconfirm AudioNormalizer.spec
```

---

## Estructura del Proyecto

```text
audio-normalizer/
├── app.py                        # WebUI local oscura en Gradio
├── main.py                       # Interfaz de línea de comandos (CLI)
├── gui.py / run_gui.py           # Interfaz alternativa en CustomTkinter
├── AudioNormalizer.spec          # Especificación de empaquetado PyInstaller
├── requirements.txt              # Dependencias de Python
└── src/
    └── audio_normalizer/
        ├── __init__.py
        ├── beat_grid.py          # Análisis de pulsos y rejilla sample-exacta a 44.1 kHz
        ├── stretcher.py          # Curva continua C^1 y motor FFmpeg rubberband
        └── pipeline.py           # Orquestador y resolución de binarios portables
```
