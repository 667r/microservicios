---
marp: true
theme: uncover
class: invert
paginate: true
footer: "Microservicios | Capacidad Vertical: Media Service"
author: "Equipo de Desarrollo"
title: "Capacidad Vertical: Gestor de Archivos y Vista Previa de Medios"
size: 16:9
---

<style>
    section {
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        text-align: left;
        padding: 40px 60px;
    }
    h1, h2, h3 {
        color: #60a5fa;
        margin-bottom: 0.3em;
    }
    h1 { font-size: 2.2em; text-align: center; }
    h2 { font-size: 1.6em; }
    h3 { font-size: 1.2em; color: #93c5fd; }
    p, li { font-size: 0.85em; line-height: 1.4; }
    table { font-size: 0.72em; width: 100%; border-collapse: collapse; margin-top: 10px; }
    th { background-color: #1e3a8a; color: #ffffff; padding: 8px 12px; text-align: left; }
    td { padding: 6px 12px; border-bottom: 1px solid #334155; }
    code { background: #1e293b; color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; }
    .badge { background: #2563eb; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.75em; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .card { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 15px; }
</style>

<!-- _class: invert lead -->
# 📂 Capacidad Vertical: Media Service
### Gestor de Archivos Adjuntos y Vista Previa de Medios
**Cátedra de Microservicios — Unidad 3**

---

## 📌 1. Problema de Usuario y Contexto

<div class="grid">
<div class="card">

### 🌐 Contexto
* Los canales de chat modernos (*Slack, Discord, Teams*) son **centros de trabajo colaborativo multimedia**.
* Los equipos necesitan compartir especificaciones en PDF, capturas de pantalla de errores y enlaces web externos.
</div>

<div class="card">

### ⚠️ Limitaciones del Chat Base
* **Solo texto plano:** El servicio `messages` admite solo strings (máx. 4.000 chars).
* **Sin soporte de binarios:** Imposible adjuntar imágenes o documentos.
* **URLs a ciegas:** Enlaces crudos sin título, imagen ni descripción.
* **Sin repositorio de canal:** No hay galería para buscar archivos compartidos.
</div>
</div>

---

## 💡 2. Propuesta de Valor y Solución

El microservicio **`media`** extiende el ecosistema del chat de forma desacoplada:

1. **Gestión de Archivos Adjuntos:** Subida (`multipart/form-data`), almacenamiento binario y descarga segura por canal.
2. **Generación Asíncrona de Link Previews:** Detección de URLs en mensajes y scraping en segundo plano de metadatos OpenGraph (*Rich Cards*).
3. **Galería de Medios por Canal:** Filtrado de archivos compartidos por categoría (`IMAGE`, `DOCUMENT`, `ARCHIVE`, etc.).
4. **Control de Cuotas de Almacenamiento:** Gestión de espacio en disco por canal sin saturar el sistema.

---

## 📖 3. Lenguaje Ubicuo (Glosario DDD)

| Concepto | Definición en el Dominio |
| :--- | :--- |
| **Archivo Adjunto (*Attachment*)** | Recurso digital (imagen, PDF) subido por un usuario y asociado a un canal. |
| **Metadatos (*Metadata*)** | Información descriptiva: nombre, tipo MIME, tamaño, hash SHA-256 y URL de descarga. |
| **Vista Previa de Enlace (*Link Preview*)** | Tarjeta resumen (título, descripción, miniatura) extraída de una URL compartida. |
| **Almacenamiento (*Media Storage*)** | Volumen físico (`/media-storage`) donde residen los archivos binarios. |
| **Cuota de Canal (*Channel Quota*)** | Límite máximo de almacenamiento acumulado asignado a un canal. |
| **Categoría de Medio (*Media Category*)** | Clasificación: `IMAGE`, `DOCUMENT`, `VIDEO`, `AUDIO`, `ARCHIVE`, `OTHER`. |

---

## 🛡️ 4. Frontera de Responsabilidad (Bounded Context)

<div class="grid">
<div class="card">

### 📦 Dentro de la frontera de `media`
* Almacenamiento binario y metadatos de archivos.
* Scraping y caché de tarjetas OpenGraph de URLs.
* Control de cuotas de disco y validación de tipos MIME.
* Base de datos exclusiva: **`chat_media`** y volumen **`media-data`**.
</div>

<div class="card">

### 🤝 Fuera de la frontera (Delegado al Núcleo)
* **Identidad y autenticidad:** Delegado a `users`.
* **Salas y membresía:** Delegado a `channels`.
* **Secuencia de mensajes de texto:** Delegado a `messages`.
* **Regla estricta:** Cero acceso directo a BDs ajenas; interacción solo vía REST y RabbitMQ.
</div>
</div>

---

## 🏗️ 5. Diagrama de Arquitectura de Microservicios

```mermaid
flowchart TD
    User(["👤 Usuario"])

    subgraph BaseChat["Núcleo del Chat"]
        UsersSvc["Users Service (:8001)"]
        ChannelsSvc["Channels Service (:8002)"]
        MessagesSvc["Messages Service (:8003)"]
    end

    Broker{{"RabbitMQ Broker\nExchange: chat (topic)"}}
    ExtWeb["🌐 Sitios Web Externos"]

    subgraph MediaExtension["Capacidad Vertical: Media"]
        MediaSvc["Media Service (:8004)"]
        MediaDB[("MongoDB: chat_media")]
        MediaStore[("Volumen: media-storage")]
        MediaSvc --- MediaDB
        MediaSvc --- MediaStore
    end

    User -->|"REST"| UsersSvc & ChannelsSvc & MessagesSvc & MediaSvc
    MessagesSvc -->|"Publica chat.message.created"| Broker
    Broker -->|"Consume chat.message.created"| MediaSvc
    MediaSvc -->|"Publica attachment.* / link_preview.*"| Broker
    MediaSvc -.->|"Valida autor/canal (REST)"| UsersSvc & ChannelsSvc
    MediaSvc -.->|"Scrape OpenGraph"| ExtWeb
```

---

## 📡 6. Contratos de Comunicación: APIs REST (Puerto 8004)

| Método | Ruta | Código HTTP | Descripción |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/channels/{channel_id}/attachments` | `201 Created` | Sube archivo adjunto (`multipart/form-data`). |
| `GET` | `/api/v1/channels/{channel_id}/attachments` | `200 OK` | Galería de archivos del canal (con filtros). |
| `GET` | `/api/v1/attachments/{attachment_id}` | `200 OK` | Consulta metadatos de un archivo específico. |
| `GET` | `/api/v1/attachments/{attachment_id}/download` | `200 OK` | Descarga stream binario del archivo. |
| `DELETE`| `/api/v1/attachments/{attachment_id}` | `204 No Content`| Elimina archivo y libera cuota del canal. |
| `GET` | `/api/v1/channels/{channel_id}/quota` | `200 OK` | Consulta cuota de almacenamiento del canal. |
| `GET` | `/api/v1/links/preview?url=...` | `200 OK` | Consulta tarjeta OpenGraph en caché. |

---

## 📬 7. Contratos de Comunicación: Eventos Asíncronos

### Broker: RabbitMQ | Exchange: `chat` (*topic*)

#### 📥 Eventos Consumidos
* `chat.message.created`:
  * Inspecciona el texto mediante Regex en busca de URLs.
  * Dispara un proceso en segundo plano para raspar los metadatos OpenGraph del sitio externo.

#### 📤 Eventos Publicados (Convención: `entidad.id.acción`)
* `attachment.{id}.uploaded`: Notifica subida exitosa de un archivo.
* `attachment.{id}.deleted`: Notifica eliminación de un archivo.
* `link_preview.{id}.generated`: Notifica que la tarjeta de previsualización está lista en caché.

---

## ⚖️ 8. Justificación de Patrones de Comunicación

<div class="grid">
<div class="card">

### 🛑 Sincrónico Request-Response (REST)
* **Dónde:** Subida (`POST`), descarga (`GET`) y validación de `users`/`channels`.
* **Justificación:** El usuario requiere confirmación inmediata del archivo cargado y transferencia directa de streams binarios de alta velocidad.
</div>

<div class="card">

### 📨 Asincrónico Event-Driven (RabbitMQ)
* **Dónde:** Detección de URLs y generación de vistas previas (*Link Previews*).
* **Justificación:** El scraping web externo tiene **latencia impredecible** (sitios caídos/lentos). Al hacerlo por eventos, el envío de chat **nunca se bloquea**.
</div>
</div>

---

## 🔄 9. Flujo Punta a Punta 1: Subida y Descarga de Archivos

```mermaid
sequenceDiagram
    autonumber
    actor Benjamin as Benjamín
    actor Manuel as Manuel
    participant Channels as Channels Service (:8002)
    participant Media as Media Service (:8004)
    participant Storage as Media Storage & DB
    participant Broker as RabbitMQ

    Benjamin->>Media: POST /api/v1/channels/ch-1/attachments (file: doc.pdf, uploader: benja)
    Media->>Channels: GET /api/v1/channels/ch-1 (Valida canal)
    Channels-->>Media: 200 OK
    Media->>Storage: Guarda binario en disco y metadatos en MongoDB
    Media->>Broker: Publica attachment.att-1.uploaded
    Media-->>Benjamin: 201 Created (Metadatos + URL de descarga)

    Manuel->>Media: GET /api/v1/channels/ch-1/attachments
    Manuel-->>Media: 200 OK [ { id: "att-1", filename: "doc.pdf", ... } ]

    Manuel->>Media: GET /api/v1/attachments/att-1/download
    Manuel-->>Media: 200 OK (Stream binario application/pdf)
```

---

## 🌐 10. Flujo Punta a Punta 2: Link Previews Asíncronos

```mermaid
sequenceDiagram
    autonumber
    actor Benjamin as Benjamín
    actor Manuel as Manuel
    participant Messages as Messages Service (:8003)
    participant Broker as RabbitMQ
    participant Media as Media Service (:8004)
    participant ExtWeb as Sitio Web Externo

    Benjamin->>Messages: POST /api/v1/channels/ch-1/messages ("Ver https://...")
    Messages->>Broker: Publica chat.message.created
    Messages-->>Benjamin: 201 Created

    Broker-->>Media: Consume chat.message.created
    Media->>ExtWeb: GET https://... (Scrape OpenGraph)
    ExtWeb-->>Media: 200 OK (og:title, og:image)
    Media->>Media: Guarda en DB chat_media (Caché)
    Media->>Broker: Publica link_preview.lp-1.generated

    Manuel->>Media: GET /api/v1/links/preview?url=https://...
    Media-->>Manuel: 200 OK {"title": "Título Web", "image_url": "..."}
```

---

<!-- _class: invert lead -->
# 🎯 Conclusión
* **Aporte de Valor:** Transforma el chat base en una plataforma multimedia rica.
* **Autonomía y Escalabilidad:** Microservicio `media` con almacenamiento y base de datos propios.
* **Desacoplamiento Total:** Comunicación asíncrona no bloqueante frente a dependencias lentas.
