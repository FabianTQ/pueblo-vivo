# Pueblo Vivo — Escenario con vida + panel de diálogos (spec)

**Fecha:** 2026-06-29
**Autor:** Fabián (con Claude Code)
**Estado:** aprobado para implementación

## 1. Objetivo y alcance

Dar vida al mundo y limpiar la lectura de los diálogos. Dos features cohesivas
(pulido visual del cliente Unity):

- **A — Escenario:** reemplazar los discos grises de localización y el suelo plano
  por un pueblo low-poly con **edificios temáticos por localización**, **piso de
  pasto**, **árboles, vallas, rocas y props**, usando el pack **KayKit "Medieval
  Hexagon" (CC0)** — mismo estilo que los aldeanos Adventurers.
- **B — Diálogos:** sustituir las burbujas de texto flotantes (que tapan a los
  personajes) por una **franja inferior tipo subtítulo** que muestra la última
  línea, sin estorbar los botones del HUD.

### Fuera de alcance (YAGNI)
- Rejilla hexagonal completa del suelo (se usa pasto plano; los edificios se
  colocan sobre el ground existente).
- Iluminación/post-procesado avanzado, animación de edificios, día/noche.
- Pack de follaje adicional (Forest) — opcional futuro.

## 2. Contexto / estado actual

- `unity/Assets/Editor/SceneBootstrap.cs` — `Build Scene` crea ground (plane
  60×60, gris), Sun, cámara (ya acercada), Brain/Village/Director/Player y hornea
  NavMesh.
- `unity/Assets/Scripts/VillageController.cs` — `CreateMarker(name,pos)` crea un
  **cilindro gris** por localización y le pone un label. `BuildWorld` coloca las
  localizaciones en un círculo de `layoutRadius=14`. `OnSay` emite la línea al log
  (`OnLog`) y llama `avatar.Say(text)`.
- `unity/Assets/Scripts/AgentAvatar.cs` — `Spawn` adjunta DOS `SpeechBubble`: una
  de diálogo (altura 1.9) y un name tag (altura 2.3). `Say(line)` muestra la de
  diálogo.
- `unity/Assets/Scripts/SpeechBubble.cs` — `TextMesh` world-space que mira a la
  cámara; usado tanto para diálogo como para el name tag.
- `unity/Assets/Scripts/DirectorUI.cs` — HUD IMGUI (`OnGUI`): barra superior,
  panel Time+Inject (izq. arriba `10,40`), Villagers (izq. medio `10,218`),
  **Event log** (abajo-izq. `10, height-180, 360×170`), Mind inspector
  (der. `width-360,40`), chat input (abajo-centro `width/2-200, height-70`).
- Render pipeline **Built-in**; materiales **Standard** con `_Color`/`_MainTex`
  (atlas). KayKit usa un atlas gradiente 1024² compartido.

## 3. Parte A — Escenario

### 3.1 Assets — KayKit Medieval Hexagon Pack (CC0)
- **Descarga (usuario, 1 vez):** https://kaylousberg.itch.io/kaykit-medieval-hexagon
  → *Download* → *"No thanks, just take me to the downloads"* → tier **free**
  (≈33 MB). Repo de referencia: github.com/KayKit-Game-Assets/KayKit-Medieval-Hexagon-Pack-1.0.
- **Ubicación:** `unity/Assets/KayKit/MedievalHexagon/`; usar la carpeta
  `fbx(unity)/`. Material Standard + atlas (mismo flujo que Adventurers), Filter
  Point en el atlas. Se commitea (CC0). Incluir `License.txt`.
- **Modelos verificados disponibles:** `well, tavern, market, church, blacksmith,
  windmill, watermill, home_A, home_B` (+ variantes de color), árboles
  (`tree_single_A/B`, `trees_*`), rocas (`rock_single_A..E`), vallas
  (`fence_wood_*`, `fence_stone_*`), props (barrel, crates, sack, tent, flags,
  wheelbarrow, market stalls), tiles de pasto.

### 3.2 EnvironmentCatalog (localización → modelo)
Mapa estático en C# (única fuente de verdad), editable:

| Localización | Modelo KayKit |
|---|---|
| tavern | tavern |
| market | market |
| bakery | windmill |
| school | church |
| well | well |
| garden | *(sin edificio: árboles + vallas alrededor)* |
| plaza | *(sin edificio: props/flags central)* |
| `home_*` | home_A / home_B (alterna; tinte de color por aldeano) |

Localización sin modelo → no se instancia edificio; el `EnvironmentDecorator`
adorna esa zona (garden con árboles, plaza con props).

### 3.3 Construcción
- **`VillageController.CreateMarker(name,pos)`** deja de crear el cilindro gris:
  resuelve `EnvironmentCatalog.ModelFor(name)`; si hay modelo, instancia el prefab
  del edificio en `pos` (con `Resources.Load<GameObject>($"Environment/{model}")`,
  fallback al cilindro gris si falta el asset). Mantiene el label del nombre a una
  altura sobre el edificio.
- **Piso:** material de pasto verde (Standard) aplicado al ground en
  `SceneBootstrap` (color/tono de pasto; opcionalmente el atlas del pack).
- **`EnvironmentDecorator`** (nuevo): tras construir el mundo, dispersa árboles,
  rocas, arbustos, vallas y props con **`System.Random` de semilla fija**
  (reproducible), en un anillo exterior y alrededor de los edificios, evitando
  solapar las localizaciones (radio `layoutRadius`).
- **Editor tool `Pueblo Vivo/Build Environment Prefabs`** (nuevo): genera los
  prefabs de edificios/props usados en `Assets/Resources/Environment/` (mismo
  patrón reproducible que `Build Avatar Prefabs`).

## 4. Parte B — Panel de diálogos (franja subtítulo)

- **`AgentAvatar`:** eliminar la `SpeechBubble` de diálogo (`_bubble`) y su uso en
  `Say`. **Conservar el name tag** (identifica a cada NPC). `Say` queda como no-op
  visual (el texto va al panel) o se elimina del flujo de burbuja.
- **`VillageController`:** añadir `event Action<string,string,string> OnDialogue`
  (speaker, target, text); emitirlo en `OnSay` (con los `DisplayName`). El
  `OnLog`/Event log se mantiene como historial.
- **`DirectorUI`:** suscribirse a `OnDialogue`, guardar la última línea + tiempo, y
  dibujar `DrawSubtitle()`: una **franja centrada** en
  `y = Screen.height - 130`, ancho `min(640, Screen.width - 740)` (para no solapar
  los paneles laterales), **semitransparente** (`GUI.color` alpha ~0.85), con
  *"Speaker → Target: texto"* envuelto a 2 líneas. Se oculta tras ~8 s sin diálogo
  nuevo. Queda por **encima** del chat input y sin tapar el centro (personajes).

## 5. Verificación
1. **Compilación C# limpia** (`read_console`, 0 errores).
2. **Visual (Play + screenshots):** edificios temáticos por localización (no
   discos), piso de pasto, árboles/vallas/props poblando el pueblo a escala
   correcta con los aldeanos; la **franja de subtítulo** muestra el diálogo en
   curso sin tapar personajes ni botones; **sin** burbujas flotantes (sí name
   tags). Flujo cerebro↔Unity intacto (move/say/snapshot/gossip).
3. **Regresión:** los aldeanos siguen caminando entre edificios (NavMesh sobre el
   mismo ground horneado).

## 6. Riesgos y mitigaciones
- **Base hexagonal en los edificios** → si traen una base de tierra/hex que choca,
  recortarla/ocultarla (desactivar el submesh) o aceptarla como pedestal.
- **Escala** edificio↔personaje (1.8u) → ajustar `Scale Factor` de import o la
  escala del prefab; verificar una casa contra un aldeano.
- **Solape decoración/edificios/NavMesh** → semilla fija + zonas de exclusión
  (radio de localización); re-hornear NavMesh tras colocar edificios si bloquean
  el paso (o marcar edificios como obstáculos y dejar caminos libres).
- **Descarga itch** ($0, CSRF) no automatizable → la hace el usuario.
- **Atlas con seams** → Filter Point / versión 128px.

## 7. Pasos de implementación (alto nivel)
1. Usuario descarga el Hexagon free y avisa la ruta.
2. Importar a `Assets/KayKit/MedievalHexagon/`; material Standard + atlas, escala.
3. `EnvironmentCatalog` (localización→modelo).
4. Editor tool `Build Environment Prefabs` → `Resources/Environment/*.prefab`.
5. `VillageController.CreateMarker` instancia edificios; ground de pasto;
   `EnvironmentDecorator` (props con semilla fija); re-hornear NavMesh si hace
   falta.
6. `AgentAvatar` quita la burbuja de diálogo; `VillageController.OnDialogue`;
   `DirectorUI.DrawSubtitle`.
7. Build Scene, Play, validar visual con screenshots; ajustar escala/posiciones.
8. Commit (assets CC0 + código) + crédito KayKit Medieval Hexagon en el README.

## 8. Notas
- Idioma: README en inglés; specs internos en español; identificadores en inglés.
- Sin datos sensibles ni secretos en assets/commits (repo público).
- La escena `Village.unity` es regenerable con `Build Scene` (está untracked).
