# Guion del clip de demo — Pueblo Vivo

**Objetivo:** clip de portafolio de **75–90 s** (+ versión corta de 30 s para redes) que
haga que un reclutador/técnico diga "¿esto corre local en una laptop?".
**Tono:** seguro, concreto, sin humo. La estrella es la **propagación del chisme**.
**Idioma:** voz en off (VO) en español; subtítulos en inglés recomendados para alcance.

---

## 0. Qué grabar (checklist de captura)

Graba con **OBS Studio** (gratis), 1080p60, dos fuentes:

- **A — Headless (garantizado, real, impresionante):** terminal corriendo el experimento.
  ```bash
  cd D:\dev\proyectos\pueblo-vivo\brain
  .venv\Scripts\activate
  python -m experiments.party --agents 5 --ticks 72 --model llama3.1:8b
  ```
  Captura: (a) el log scrolleando con `talk` / `gossip spread: X -> Y`, y (b) el bloque
  final **RESULTS** con el `PASS`. Usa una fuente grande y tema oscuro en la terminal.
  > Tip: si quieres que se vea fluido, graba y luego acelera 4–8× en edición; deja a
  > velocidad real solo los momentos clave (un `gossip spread` y el RESULTS).

- **B — Unity (cuando hagas *Build Scene* + Play):** el modo director es el visual clave.
  Prepara la toma así:
  1. Arranca el cerebro: `uvicorn pueblo.server:app --host 127.0.0.1 --port 8765`
     (con `PUEBLO_AGENTS=6`).
  2. En Unity, Play → en el HUD pon **5x** o **10x** para que el día avance rápido.
  3. Tomas a capturar:
     - Vista general del pueblo con los aldeanos caminando entre lugares.
     - **Clic en un aldeano → panel de Mente** (memorias, plan, "knows the secret: true").
     - **Inyectar un evento** (escribe algo y pulsa *Inject*) y mostrar cómo reaccionan.
     - **Líneas de chisme** saltando entre dos agentes.
     - **Modo personaje:** acércate a un NPC y escríbele algo; muestra su respuesta.

> Estado actual: los aldeanos son cápsulas placeholder. Para el clip "bonito",
> primero cámbialas por arte low-poly (Synty/Kenney/Mixamo). Si grabas YA, encuádralo
> como "prototipo funcional / gameplay programmer view" — sigue impresionando porque
> lo que vende es la IA, no el arte.

---

## 1. Estructura (storyboard shot-by-shot)

| t (s) | Visual (qué se ve) | Voz en off (ES) | Texto en pantalla |
|---|---|---|---|
| 0–7 **HOOK** | Plano del pueblo (B) o el log con un `gossip spread` (A), corte rápido. | "Estos personajes no tienen diálogos escritos. Conversan, recuerdan y cambian de planes en tiempo real… con una IA que corre en mi propia laptop." | **Pueblo Vivo** · NPCs con IA generativa, 100% local |
| 7–20 **CONCEPTO** | Split: NPC genérico repitiendo línea vs. tus agentes. Logo del paper. | "Los NPCs de siempre repiten lo mismo en bucle. Aquí cada aldeano tiene memoria, personalidad y una agenda propia. Es una reimaginación del paper *Generative Agents* de Stanford… pero sin nube: todo offline en una RTX 4060." | Inspirado en *Generative Agents* (Stanford, 2023) · Sin nube · Sin APIs |
| 20–30 **EL SETUP** | Modo director: clic en "Maria", se abre su mente. Luego escribo/inyecto la noticia de la fiesta. | "Le cuento a UNA sola aldeana que hay una fiesta esta noche en la plaza. A nadie más." | El experimento: ¿se propaga el rumor? |
| 30–52 **EL CHISME (clímax)** | Acelero el tiempo (5x). Los agentes se cruzan; saltan líneas de chisme; el log muestra `Maria → Diego → Sofia → Carlos`. | "Y entonces empieza a correr la voz. Diego se entera por María… y se lo cuenta a Sofía. Sofía a Carlos. Nadie programó esa cadena: emerge sola de sus conversaciones." | Boca a boca · cadena emergente |
| 52–62 **EL PAGO** | Reloj llega a las 17:00; los agentes convergen en la plaza. Corte al RESULTS del headless: `4 by word of mouth`, `PASS`. | "Al caer la tarde, los que se enteraron aparecen en la plaza, a la hora correcta. Cinco de cinco lo supieron; cuatro por boca a boca." | 5/5 informados · 4 por cadena · ✅ |
| 62–80 **BAJO EL CAPÓ** | Diagrama de arquitectura (usa el del README/spec) + flash de `pytest` en verde. | "Por debajo: un cerebro en Python con memoria, recuperación por relevancia, reflexión y planificación, hablando con Unity por WebSocket. Simulación por turnos para que una sola GPU lo mueva. Y con tests." | Python (cerebro) + Unity (cliente) · memory · retrieval · reflection · planning · 35 tests ✅ |
| 80–88 **CIERRE** | Plano final del pueblo / tu nombre. | "Sin nube, sin APIs, sin costo por token. Solo mi GPU y un pueblo que cobra vida." | **Pueblo Vivo** · [tu nombre] · GitHub /usuario · Unity 6 · Ollama · FastAPI |

---

## 2. Voz en off, texto corrido (para leer de una)

> Estos personajes no tienen diálogos escritos. Conversan, recuerdan y cambian de
> planes en tiempo real, con una IA que corre en mi propia laptop.
>
> Los NPCs de siempre repiten lo mismo en bucle. Aquí cada aldeano tiene memoria,
> personalidad y una agenda propia. Es una reimaginación del paper *Generative Agents*
> de Stanford, pero sin nube: todo offline en una RTX 4060.
>
> Le cuento a una sola aldeana que esta noche hay una fiesta en la plaza. A nadie más.
> Y entonces empieza a correr la voz: Diego se entera por María y se lo cuenta a Sofía;
> Sofía a Carlos. Nadie programó esa cadena, emerge sola de sus conversaciones.
>
> Al caer la tarde, los que se enteraron aparecen en la plaza, a la hora correcta.
> Cinco de cinco lo supieron; cuatro, por boca a boca.
>
> Por debajo hay un cerebro en Python — memoria, recuperación por relevancia, reflexión
> y planificación — hablando con Unity por WebSocket, y una simulación por turnos para
> que una sola GPU lo mueva. Con tests.
>
> Sin nube, sin APIs, sin costo por token. Solo mi GPU y un pueblo que cobra vida.

*(≈ 150 palabras ≈ 80 s a ritmo natural.)*

---

## 3. Versión corta 30 s (para LinkedIn/X/Shorts)

1. **0–4 s:** texto grande "NPCs que piensan con IA — 100% local" sobre el pueblo.
2. **4–18 s:** "Le digo a UNO que hay fiesta…" → time-lapse del chisme propagándose +
   líneas saltando + log `Maria → Diego → Sofia → Carlos`.
3. **18–25 s:** llegan a la plaza + `4 por boca a boca · PASS`.
4. **25–30 s:** end card: "Python + Unity + Ollama · RTX 4060 · sin nube" + tu @.

---

## 4. Tarjetas (lower-thirds / end card)

- **Title card:** `Pueblo Vivo` / *Generative agents que viven en tu GPU*.
- **Badges de stack:** `Unity 6` · `Ollama (llama3.1:8b)` · `Python / FastAPI` · `WebSocket` · `nomic-embed`.
- **End card:** tu nombre + rol ("Ing. de Sistemas — IA / Gameplay") + GitHub + "demo 100% local, sin nube".

---

## 5. Producción

- **Música:** instrumental cálido/curioso, sube en el clímax del chisme (t≈30). YouTube
  Audio Library / Uppbeat (libres).
- **Ritmo:** cortes de 2–4 s; acelera el time-lapse, respira en el `gossip spread` y el `PASS`.
- **Subtítulos:** quema subtítulos (mucha gente ve sin audio). Versión EN para alcance.
- **Edición:** DaVinci Resolve o CapCut (gratis). Resolución 1080p; 9:16 aparte para Shorts.
- **Duración final ideal:** 75–90 s en portafolio; 30 s en redes.

---

## 6. Pitch de 1 línea (para el caption/descrición)

> Construí un pueblo donde los NPCs conversan, recuerdan y propagan rumores entre sí
> usando un LLM local — una reimaginación en Unity del paper *Generative Agents* de
> Stanford, corriendo 100% offline en una RTX 4060.
