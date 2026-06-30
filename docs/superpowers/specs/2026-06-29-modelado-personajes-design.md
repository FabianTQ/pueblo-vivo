# Pueblo Vivo — Modelado de personajes (spec)

**Fecha:** 2026-06-29
**Autor:** Fabián (con Claude Code)
**Estado:** aprobado para implementación

## 1. Objetivo y alcance

Reemplazar el render *placeholder* de cada NPC —hoy una cápsula de color sólido—
por un **humanoide low-poly riggeado y animado**, uno **distinto por rol** de
aldeano, conservando intacto el resto del sistema (NavMesh, speech bubbles, name
tags, highlight del Director y todo el flujo cerebro↔Unity por WebSocket).

El arte proviene del pack **KayKit "Adventurers"** (Kay Lousberg), licencia
**CC0 1.0** — redistribuible en el repo público sin atribución.

### Dentro de alcance
- Importar y configurar los modelos KayKit (FBX, rig Humanoid, materiales URP).
- Un `AnimatorController` compartido con blend **idle ↔ caminar** según la
  velocidad del `NavMeshAgent`; gesto de saludo (`Cheer`) al iniciar conversación.
- Mapeo **ocupación → modelo** leído del snapshot del cerebro.
- Refactor de `AgentAvatar` y `VillageController` para instanciar el modelo por rol.
- Un Editor tool reproducible que genera los prefabs de avatar (filosofía
  "todo por código, cero setup manual de escena").
- Verificación: compilación limpia, test edit-mode del catálogo y validación
  visual en Play.

### Fuera de alcance (YAGNI; mejoras futuras)
- Rediseñar las localizaciones (siguen siendo discos/cilindros grises).
- Dar modelo al Player (sigue siendo cápsula; en modo Character casi no se ve).
- Animaciones de combate u otras más allá de idle/walk/run/cheer.
- El pack adicional "KayKit Character Animations" (no necesario: los clips
  requeridos ya vienen en Adventurers).

## 2. Contexto / estado actual

- `unity/Assets/Scripts/AgentAvatar.cs` — `Spawn(id, name, pos, color)` crea
  `GameObject.CreatePrimitive(PrimitiveType.Capsule)`, le añade `NavMeshAgent`,
  pinta el material con un color de paleta, y adjunta dos `SpeechBubble`
  (diálogo a `y=2.2`, name tag a `y=2.7`). Métodos: `GoTo` (NavMesh), `Say`
  (bubble), `SetHighlight` (cambia el color del renderer a amarillo).
- `unity/Assets/Scripts/VillageController.cs` — `BuildWorld(snapshot)` crea los
  marcadores de localización (cilindros grises) y un avatar por agente, eligiendo
  un color de una paleta de 7. **Hoy solo lee `id`, `name`, `location` del
  snapshot; NO lee `occupation`.** `Handle(ev)` despacha move/say/clock/etc.
- `unity/Assets/Editor/SceneBootstrap.cs` — `Pueblo Vivo/Build Scene` arma la
  escena por código: ground (plane 60×60), Sun, cámara cenital, Brain, Village
  (+GossipGraph), Player (cápsula), DirectorUI, y **hornea el NavMesh** con
  `NavMeshSurface` (`collectObjects=All`, `BuildNavMesh()`). Guarda
  `Assets/Scenes/Village.unity`.
- `brain/pueblo/runner.py` `_snapshot_impl` **ya expone `occupation`** por agente
  (junto a `id`, `name`, `location`, `action`). El cliente no necesita cambios
  en el lado Python.
- `brain/pueblo/scenarios.py` define el reparto y sus ocupaciones:
  maria=innkeeper (host), diego=bartender, lucia=baker, carlos=farmer,
  sofia=teacher, pedro=merchant, elena=gardener.
- `unity/Assets/Scripts/BrainClient.cs` — tolera el orden de mensajes: si un
  evento llega antes del `snapshot`, `VillageController` no encuentra el agente y
  lo ignora; el `snapshot` reconstruye el mundo. (Sin cambios en esta tarea.)

## 3. Assets — KayKit "Adventurers" (CC0)

- **Descarga (la hace el usuario, 1 vez):** https://kaylousberg.itch.io/kaykit-adventurers
  → *Download Now* → *"No thanks, just take me to the downloads"* → **`Free 2.0`**
  (≈12 MB). Es el único archivo necesario.
- **Ubicación:** descomprimir en `unity/Assets/KayKit/Adventurers/`. Estructura:
  `Characters/fbx/*.fbx` (+ `*_texture.png`), `Assets/` (accesorios, no usados),
  `Textures/`, `LICENSE.txt`.
- **Commit:** los assets se versionan en el repo público (el `.gitignore` no
  ignora `Assets/`). CC0 ⇒ seguro. ≈12 MB ⇒ sin Git LFS. Se incluye `LICENSE.txt`
  del pack y se añade una nota de créditos en el README (cortesía, no obligatoria
  en CC0).
- **Contenido verificado** (parseando el FBX real): cada personaje trae 76 clips
  *baked*, incluidos `Idle`, `Walking_A/B/C`, `Running_A`, `Cheer`. Rig
  `Rig_Medium`, compatible Unity **Humanoid**. Texturas: atlas PNG 1024² plano.
- **Modelos free (6):** Knight, Barbarian, Rogue, **Rogue Hooded**, Mage, Ranger.

## 4. Mapeo ocupación → modelo (por defecto, editable en código)

| Agente | Ocupación | Modelo |
|--------|-----------|--------|
| maria (host) | innkeeper | Mage |
| diego | bartender | Barbarian |
| lucia | baker | Ranger |
| carlos | farmer | RogueHooded |
| sofia | teacher | Knight |
| pedro | merchant | Rogue |
| elena | gardener | *(7º; reuso con tinte, o Druid del tier Extra)* |

El mapeo vive en un único punto (catálogo) y es trivial de cambiar. Si una
ocupación no tiene modelo asignado, se cae a un modelo por defecto + tinte (nunca
rompe). El server corre con 6 agentes por defecto, así que elena solo aparece si
`PUEBLO_AGENTS=7`.

## 5. Arquitectura técnica

### 5.1 Importación de assets (configuración de import)
- Importar los FBX de `Characters/fbx/`. Rig tab: **Animation Type = Humanoid**.
  El primer modelo: **Create From This Model**; los otros 5:
  **Copy From Other Avatar** apuntando al avatar del primero (un solo avatar
  compartido `Rig_Medium`, retargeting automático de clips).
- Materiales → **URP/Lit**: como el atlas es plano (sin normal/metallic), basta
  un material URP/Lit por personaje con el PNG en *Base Map*. Atlas:
  **Filter Mode = Point** (los colores son bandas duras; el filtrado bilineal
  las difumina).
- **Apply Root Motion = OFF** (el movimiento lo conduce el NavMesh). Confirmar
  *Loop Time* en Idle/Walking/Running.

### 5.2 Generación de prefabs — Editor tool
`Pueblo Vivo/Build Avatar Prefabs` (nuevo, en `unity/Assets/Editor/`):
- Para cada modelo configurado, instancia el FBX, le añade `NavMeshAgent`
  (radius 0.35, height ~1.8 ajustado al modelo, speed 3.5), `Animator`
  (controller `VillagerAnimator`), y `AgentAvatar`; guarda el prefab en
  `unity/Assets/Resources/Avatars/<rol>.prefab`.
- Reproducible y commiteado; mantiene la filosofía "cero setup manual".

### 5.3 AnimatorController `VillagerAnimator`
- Asset commiteado (`unity/Assets/Resources/Avatars/VillagerAnimator.controller`).
- **Blend Tree 1D** sobre `float Speed`: Idle (0.0) → Walking_A (~2.0) →
  Running_A (~5.5).
- **Trigger `Cheer`** (gesto de saludo) disparado al iniciar conversación.
- Apply Root Motion OFF. Un solo controller para los 6 (avatar Humanoid compartido).

### 5.4 Refactor `AgentAvatar`
- `Spawn(role, id, name, pos, tint?)`:
  `Resources.Load<GameObject>($"Avatars/{role}")`; si es null → **fallback** a la
  cápsula actual (el repo nunca queda roto si faltan los assets).
- Cachea el `Animator`; en `Update` setea `Speed = nav.velocity.magnitude`
  (suavizado) → blend idle/walk.
- `GoTo`/`Say` igual; alturas de bubble/name tag ajustadas a la altura del modelo
  (parámetros expuestos, p.ej. diálogo ~1.9, name tag ~2.3).
- `SetHighlight(on)`: vía `MaterialPropertyBlock` (emisión amarilla) en lugar de
  reescribir el color base, para no destruir la textura del modelo.
- `Cheer()`: dispara el trigger del Animator (llamado desde `VillageController`
  en `talk_start`).

### 5.5 `VillageController`
- `BuildWorld`: leer `occupation` del snapshot, resolver el rol→modelo vía el
  catálogo, y llamar `AgentAvatar.Spawn(role, …)`.
- `talk_start`: además de loguear, invocar `Cheer()` en los avatares `a` y `b`.

### 5.6 Catálogo ocupación→rol
Mapa estático en C# (p.ej. `AvatarCatalog`), única fuente de verdad para el
mapeo de §4, consultado por `VillageController` y el Editor tool.

## 6. Animación
- **Base:** Idle ↔ Walking_A según velocidad del NavMesh; Running_A al ir rápido.
- **Toque:** `Cheer` al iniciar una conversación (`talk_start`) — vida sin coste,
  refuerza el momento "wow" del chisme. (Si molesta, se quita borrando un trigger.)

## 7. Verificación
1. **Compilación C# limpia** (`read_console`, 0 errores).
2. **Edit-mode test** (`unity/Assets/Tests/`): para cada ocupación del reparto el
   catálogo resuelve un rol; `Resources.Load` encuentra el prefab; el prefab tiene
   `Animator` + `NavMeshAgent` + `AgentAvatar`.
3. **Visual (Play + screenshots):** 6 humanoides **distintos** caminando
   *animados* a sus localizaciones, con name tags, bubbles y highlight del
   Director funcionando; flujo move/say/snapshot intacto; HUD "connected".
4. **Regresión:** el experimento del chisme sigue propagándose en pantalla.

## 8. Riesgos y mitigaciones
- **Ranger free no byte-confirmado** → si falta en el zip 2.0, sustituir por otra
  variante (p.ej. duplicar Rogue con tinte). El catálogo lo absorbe.
- **Root motion** podría no ser in-place → si hay deriva, *Root Transform
  Position (XZ) → Bake Into Pose*.
- **Escala de import** → verificar altura ~1.8 u; ajustar `Scale Factor` y radios
  del NavMeshAgent / alturas de bubble.
- **Loop Time off** por defecto en algún clip → revisar (si no, el walk "salta").
- **Atlas con filtrado** → Filter Mode = Point.
- **Tamaño repo** +≈12 MB → aceptable; documentar el origen CC0.

## 9. Pasos de implementación (alto nivel)
1. Usuario descarga `Free 2.0` y avisa la ruta.
2. Descomprimir a `Assets/KayKit/Adventurers/`; configurar import (Humanoid,
   avatar compartido, URP, atlas Point).
3. Crear `VillagerAnimator.controller` (Blend Tree + trigger Cheer).
4. `AvatarCatalog` (mapa ocupación→modelo).
5. Editor tool `Build Avatar Prefabs` → `Resources/Avatars/*.prefab`.
6. Refactor `AgentAvatar` (instanciar prefab, animar, highlight MPB, alturas) y
   `VillageController` (leer occupation, Cheer en talk_start).
7. Edit-mode test del catálogo/prefabs.
8. Build Scene, Play, validar visual con screenshots; iterar escala/alturas.
9. Commit (assets CC0 + código + test) y nota de créditos en README.

## 10. Notas
- El idioma del repo público: README en inglés; los specs internos en español
  (consistente con el spec existente). Los identificadores de código en inglés.
- Sin datos sensibles ni credenciales en los assets/commits (repo público).
