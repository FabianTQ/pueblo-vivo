# Pueblo Vivo — Diseño (spec)

**Fecha:** 2026-06-29
**Autor:** Fabián (con Claude Code)
**Estado:** aprobado para implementación

## 1. Visión

Un juego/simulación donde un pueblo pequeño (~6-8 habitantes) está poblado por
**agentes generativos**: NPCs cuya conducta no está scripteada, sino que emerge de
una arquitectura cognitiva (memoria + recuperación + reflexión + planificación)
alimentada por un **LLM local (Ollama) en la RTX 4060**. Es una reimplementación,
en local y en Unity, de las ideas del paper *Generative Agents: Interactive
Simulacra of Human Behavior* (Park et al., 2023, "Smallville").

El jugador es **híbrido**: puede encarnar un personaje y caminar/conversar con los
agentes, o pasar a **modo director** para pausar/acelerar el tiempo, abrir la
"mente" de un agente (sus memorias, plan y relaciones), inyectar eventos y
visualizar cómo se propaga la información.

### 1.1 El "wow" central (criterio de aceptación)

**Propagación de chismes/información.** Se le cuenta a UN agente un hecho nuevo
(p.ej. *"María va a dar una fiesta el sábado a las 5pm en la plaza"*). Al correr el
día simulado, la noticia se propaga de boca en boca por conversaciones entre
agentes, algunos re-planifican y **aparecen en el lugar/hora correctos**.

Métricas medibles de la demo:
- **Difusión:** nº de agentes que conocen el hecho al final del día sin habérselo
  dicho directamente (vía cadenas de conversación).
- **Asistencia:** nº de agentes que re-planificaron para estar en la plaza el
  sábado a las 5pm.
- **Ruta de propagación:** grafo "quién se lo dijo a quién" (visualizable).

Umbral de éxito del vertical slice: con 7 agentes, ≥4 se enteran por cadena (no por
inyección directa) y ≥2 asisten, de forma reproducible entre corridas.

## 2. Alcance

### En alcance (vertical slice)
- 6-8 agentes con identidad, rasgos, ocupación y relaciones iniciales.
- Mundo pequeño: ~6-10 ubicaciones (casas, taberna, plaza, tienda, etc.).
- Arquitectura cognitiva completa: memory stream, retrieval, reflexión, planificación, conversación.
- Simulación por ticks con cola de razonamiento serial (1 GPU).
- Cliente Unity 3D low-poly: modo personaje + modo director.
- Voz: STT (whisper) entrada + TTS (Piper) salida, en CPU.
- Experimento de la fiesta reproducible + métricas.

### Fuera de alcance (no-goals)
- Escala tipo Smallville (25 agentes, API en la nube).
- Combate, economía compleja, progresión de "juego" tradicional.
- Multijugador.
- Generación procedural de mundo.
- Empaquetado/instalador distribuible (se ejecuta desde el proyecto).

## 3. Arquitectura

Dos procesos en localhost, 100% offline:

### 3.1 Cerebro — Python (FastAPI + WebSocket)
Corre toda la lógica difícil. Subcomponentes:
- **`config`**: modelos, pesos de retrieval, parámetros de tiempo, rutas.
- **`llm`**: cliente Ollama (chat + embeddings) con timeouts, reintentos y modo JSON.
- **`memory`**: `Memory`, `MemoryStream`, importancia, embeddings, retrieval, persistencia SQLite.
- **`reflection`**: disparador por umbral de importancia + síntesis de insights.
- **`planning`**: plan diario (grueso → horario → fino) + re-planificación por interrupción.
- **`conversation`**: diálogo por turnos entre agentes y con el jugador + resumen y writeback.
- **`agent`**: entidad agente (identidad, estado, ubicación, memoria, plan).
- **`world`**: ubicaciones, reloj/ticks, registro de agentes, co-localización.
- **`simulation`**: bucle de ticks, cola de razonamiento serial, inyección de eventos.
- **`server`**: FastAPI/WebSocket; protocolo cerebro↔Unity; prioridad para diálogo del jugador.

La cognición es **librería pura testeable sin Unity ni servidor** (los tests y el
experimento de la fiesta la ejercitan directamente contra Ollama).

### 3.2 Cliente — Unity 6 (C#)
Solo render + input + UI. Subcomponentes:
- Mundo 3D low-poly + NavMesh; avatares que caminan según su plan.
- Modo personaje: character controller, diálogo por proximidad, captura de micrófono.
- Modo director: control de tiempo, inspector de mente, inyección de eventos, viz de chisme.
- Burbujas de diálogo + reproducción de audio (TTS).
- `WebSocketClient` C# que habla con el cerebro.

### 3.3 Reparto de hardware (RTX 4060, 8 GB)
- **GPU:** LLM de cognición + render 3D low-poly.
- **CPU:** STT (whisper.cpp) + TTS (Piper).
- Modelo de cognición configurable; por defecto un 3-4B (p.ej. `llama3.2:3b`) para
  convivir con el render; `qwen2.5:7b`/`llama3.1:8b` como opción de mayor calidad
  cuando Unity no compite (corridas headless).

## 4. Modelo cognitivo (detalle)

### 4.1 Memory stream
Registro append-only de `Memory`:
- `id`, `agent_id`, `kind` (observation | conversation | reflection | plan),
- `text`, `created_tick`, `last_access_tick`, `importance` (1-10), `embedding`,
- opcional `citations` (ids que originaron una reflexión).

`importance` se puntúa una vez al crear (LLM: "¿qué tan trascendente es esto, 1-10?"
con fallback heurístico). `embedding` vía `nomic-embed-text`.

### 4.2 Retrieval
Para una consulta `q`, puntuar cada memoria por suma ponderada normalizada:
- **recencia** = `decay ** (now - last_access_tick)` (decay≈0.99 por tick),
- **importancia** = `importance / 10`,
- **relevancia** = coseno(`emb(q)`, `emb(memoria)`).

`score = w_rec*rec + w_imp*imp + w_rel*rel` (pesos configurables, default 1/1/1).
Tomar top-k (default 10). Similitud por fuerza bruta en numpy (N pequeño → trivial).
Actualizar `last_access_tick` de las recuperadas.

### 4.3 Reflexión
Cuando la suma de importancia de memorias recientes supera un umbral (default 150):
1. LLM genera las 2-3 preguntas más salientes sobre lo reciente.
2. Por cada pregunta, retrieve top-k y el LLM sintetiza 1-3 insights con citas.
3. Los insights se guardan como `reflection` (importancia alta). Habilita relaciones/opiniones emergentes.

### 4.4 Planificación
- Al inicio del día: plan grueso (5-8 puntos) → horario por bloques → acción actual.
- El plan se guarda como memorias `plan`.
- **Re-planificación:** cuando una observación/charla relevante (p.ej. la fiesta)
  contradice o enriquece el plan, el agente decide si ajustar su agenda.

### 4.5 Conversación
- Dos agentes co-localizados que deciden hablar intercambian turnos (límite de turnos).
- Cada turno: retrieve memorias relevantes + diálogo-hasta-ahora → frase en personaje.
- Al cerrar: resumen de la charla → memoria `conversation` en AMBOS (canal del chisme).
- Diálogo con el jugador: igual, pero con **prioridad** en la cola.

## 5. Bucle de simulación y tiempo

- Reloj simulado desacoplado del reloj real. `1 tick = 10 min simulados` (config).
- La mayoría de ticks son **gratis**: el agente ejecuta su acción planeada (moverse).
- El LLM solo se invoca en **eventos cognitivos**: fin de paso de plan, observación
  saliente, conversación, reflexión, plan diario.
- Estos eventos entran en **una cola asíncrona servida en serie** por Ollama.
- El **diálogo del jugador tiene prioridad** para responsividad.
- El director puede **pausar / acelerar** (procesa ticks en lote).

## 6. Stack técnico

- **Cerebro:** Python 3.11+ (objetivo de venv; el host tiene 3.13 — ver riesgos),
  `httpx`/`requests`, `numpy`, `fastapi`, `uvicorn`, `websockets`, `pytest`.
  Persistencia: `sqlite3` (stdlib). Sin Docker para jugar.
- **LLM/embeddings:** Ollama (chat 3-8B + `nomic-embed-text`).
- **Voz:** Piper (TTS, ONNX/CPU) + whisper.cpp o faster-whisper (STT, CPU).
- **Cliente:** Unity 6 (`6000.2`/`6000.3`), C#, paquete `NativeWebSocket` o
  `System.Net.WebSockets`, NavMesh (AI Navigation), arte low-poly (Kenney/Synty/Mixamo).
- **Tests:** pytest (cerebro), Unity Test Framework EditMode/PlayMode (cliente).

## 7. Protocolo cerebro↔Unity (WebSocket, JSON)

Mensajes **Cerebro→Unity**: `agent_move {agent_id, to_location, path?}`,
`agent_say {agent_id, text, audio_b64?}`, `agent_state {agent_id, ...}`,
`clock {tick, sim_time}`, `mind_dump {agent_id, memories[], plan, relationships}`,
`gossip_edge {from, to, fact_id}`.

Mensajes **Unity→Cerebro**: `player_say {agent_id, text}`,
`inject_event {text, location?, agents?}`, `time_control {action, speed}`,
`inspect {agent_id}`, `set_mode {character|director}`.

## 8. Fases de implementación

Cada fase es spec→plan→build→test verificable.

- **F0 — Fundaciones:** repo, deps, cliente Ollama, benchmark de latencia 3b/7b/8b en la 4060.
- **F1 — Núcleo cognitivo (headless, Python):** memory/retrieval/reflexión/planning/
  conversación + sim por ticks. **Validar experimento de la fiesta en texto puro.** *(la parte de mayor riesgo/valor; probada en vivo por el agente)*
- **F2 — Servidor + protocolo:** FastAPI/WebSocket + cola con prioridad; cliente de prueba Python.
- **F3 — Mundo Unity:** escena 3D low-poly + NavMesh + avatares que se mueven por plan + reloj.
- **F4 — Modo personaje:** controller + diálogo por proximidad + el jugador entra al chisme.
- **F5 — Modo director:** tiempo, inspector de mente, inyección, viz de propagación.
- **F6 — Voz:** Piper TTS + whisper STT (CPU).
- **F7 — Pulido + demo:** escenario reproducible de la fiesta, overlay de métricas, README, clip.

## 9. Riesgos y mitigaciones

- **Latencia del LLM** → tiempo simulado acelerable + cola serial + acciones baratas; diálogo del jugador priorizado; modelo 3-4B por defecto.
- **VRAM (8 GB) con 3D + LLM** → low-poly + modelo 3-4B; STT/TTS en CPU; resolución/calidad de render acotadas.
- **Salida del LLM no estructurada (JSON inválido)** → modo JSON de Ollama + parsers tolerantes + reintentos + fallbacks heurísticos. Modelos fuertes en formato (qwen2.5).
- **Python 3.13 sin wheels (whisper/piper)** → venv 3.11/3.12 dedicado si hace falta, o binarios ONNX/CLI; el núcleo cognitivo solo usa stdlib+numpy (3.13 OK).
- **Unity no testeable headless por el agente** → C# + escena por script con placeholders + tests en batchmode donde se pueda; pasos de Editor exactos para el usuario.
- **Coste de cómputo de reflexión** → umbral configurable; reflexionar poco y barato.
- **No determinismo** → semillas donde aplique; criterio de aceptación tolerante a estocasticidad (umbral, no exactitud).

## 10. Definición de "terminado" (lo verificable por el agente)

- Núcleo cognitivo + sim por ticks **corriendo contra Ollama real**, con suite de
  tests verde, y el **experimento de la fiesta** cumpliendo el umbral de aceptación
  de forma reproducible (texto headless).
- Servidor WebSocket validado con cliente de prueba Python.
- Pipeline de voz validado a nivel de archivos (wav generado por TTS, transcrito por STT).
- Cliente Unity: todo el C# + escena por script + tests; lo no verificable en vivo
  queda documentado con pasos de Editor.
