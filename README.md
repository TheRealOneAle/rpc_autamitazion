# 🏆 RPC Automatización - Sistema Integral de Scoreboard y Publicación en Redes

Sistema basado en arquitectura de **microservicios** diseñado para la **Red de Programación Competitiva (RPC)**. Automatiza en tiempo real el seguimiento del concurso en la plataforma BOCA, la generación gráfica del Top 10 con banderas y globos representativos, y la difusión programada de los resultados en Facebook.

---

## 📑 Tabla de Contenido

- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Microservicios](#-microservicios)
  - [1. boca-scraper](#1-boca-scraper)
  - [2. generarglobos](#2-generarglobos)
  - [3. generartabla](#3-generartabla)
  - [4. ms4-publisher](#4-ms4-publisher)
  - [5. Nginx (API Gateway)](#5-nginx-api-gateway)
- [Funcionalidades Principales e Innovaciones](#-funcionalidades-principales-e-innovaciones)
- [Requisitos Previos](#-requisitos-previos)
- [Variables de Entorno (.env)](#-variables-de-entorno-env)
- [Instalación y Despliegue con Docker](#-instalación-y-despliegue-con-docker)
- [Guía de Uso del Panel Web](#-guía-de-uso-del-panel-web)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Solución de Problemas Comunes](#-solución-de-problemas-comunes)

---

## 🏗️ Arquitectura del Sistema

```
                        ┌──────────────────────────────┐
                        │      Cliente / Navegador     │
                        └──────────────┬───────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │    Nginx (API Gateway :8001)      │
                     └─┬───────────────┬───────────────┬─┘
                       │               │               │
      /boca-scraper    │  /generartabla│ /facebook-table/publisher
                       ▼               ▼               ▼
            ┌──────────────┐   ┌──────────────┐   ┌───────────────────────────┐
            │ boca-scraper │◄──┤ generartabla │◄──┤       ms4-publisher       │
            │   (:3001)    │   │   (:5002)    │   │          (:8003)          │
            └──────┬───────┘   └──────┬───────┘   └─────────────┬─────────────┘
                   │                  │                         │
                   │           /globo │                         │
                   │           ───────▼───────                  ▼
                   │          ┌──────────────┐           ┌──────────────┐
                   │          │generarglobos │           │ ms4-postgres │
                   │          │   (:5000)    │           │ (PostgreSQL) │
                   │          └──────┬───────┘           └──────────────┘
                   │                 │
                   ▼                 ▼
          ┌──────────────────────────────────┐
          │     BOCA Online Contest / BD     │
          │ (PostgreSQL / Web Scraping BOCA) │
          └──────────────────────────────────┘
```

---

## 🧩 Microservicios

### 1. `boca-scraper` (Puerto `3001`)
Microservicio en **Flask** encargado de interactuar con la plataforma BOCA del concurso.
- **Extracción Híbrida**:
  - **Opción 1 (Direct DB)**: Conexión directa a la base de datos PostgreSQL de BOCA con resolución dinámica de nombre `rpc_{año}_{contest}` (ej: `rpc_2026_06`) para consultar `problemtable`.
  - **Opción 2 (Web Scraping Administrativo)**: Login automático como administrador (`silux`/`ovallos.`) en `admin/problem.php` para extraer letras y colores exactos en hexadecimal.
  - **Fallback Público**: Si no hay credenciales de administrador para un concurso (ej: `2026/05`), realiza login automático como usuario público de tablero (`board` sin contraseña) y consulta `score/score.php` con paleta de colores estándar.
- **Endpoints**:
  - `GET /api/ranking?contest=YEAR/CONTEST`: Ranking actual y estadísticas de problemas.
  - `GET /api/problems?contest=YEAR/CONTEST`: Lista de problemas con letra y color hexadecimal.
  - `GET /api/teams?contest=YEAR/CONTEST`: Listado de equipos participantes y países.
  - `GET /api/teams/ac?contest=YEAR/CONTEST`: Envíos aceptados por problema.
  - `GET /health`: Chequeo de estado.

---

### 2. `generarglobos` (Puerto `5000`)
Microservicio en **Flask + Pillow (PIL)** que genera y sobreescribe dinámicamente las imágenes `.png` de los globos.
- Consulta los colores en tiempo real (directo a PostgreSQL o a `boca-scraper`).
- Aplica composición alfa con plantillas vectoriales/rasterizadas (`bigballoon.png` y `bigballoontransp.png`).
- Organiza la caché de imágenes por competencia en `globosgenerados/{year}_{contest}/`.
- **Endpoints**:
  - `GET /globo/<letter>.png?contest=YEAR/CONTEST`: Retorna la imagen del globo solicitado.
  - `POST /generate?contest=YEAR/CONTEST`: Genera y sobreescribe todos los globos de la competencia.
  - `GET /health`: Chequeo de estado.

---

### 3. `generartabla` (Puerto `5002`)
Microservicio en **Flask + WeasyPrint** que renderiza la imagen final del Top 10 Latinoamericano.
- Incrusta banderas SVG oficiales de cada país de Latinoamérica (Colombia, México, Brasil, Perú, Argentina, Cuba, etc.) y el logo oficial de la RPC.
- Descarga y coloca los globos resueltos para cada equipo en el Top 10.
- Convierte la plantilla HTML/CSS a una imagen JPEG de alta calidad (`ranking_{year}_{contest}.jpg`).
- **Endpoints**:
  - `POST /generate?contest=YEAR/CONTEST`: Renderiza la tabla y genera el archivo JPEG.
  - `GET /ranking.jpg?contest=YEAR/CONTEST`: Entrega la última imagen generada.
  - `GET /health`: Chequeo de estado.

---

### 4. `ms4-publisher` (Puerto `8003`)
Aplicación principal en **Django + Django REST Framework + APScheduler + PostgreSQL**.
- **Panel Web**: Dashboard interactivo para previsualizar la tabla, redactar textos y monitorear el estado.
- **Autenticación Google OAuth 2.0**:
  - Control de acceso protegido por **Whitelist** (`AllowedEmail` en BD y `ALLOWED_EMAILS` en `.env`).
  - Auto-registro seguro del primer usuario cuando la lista está vacía.
- **Publicador en Facebook (Meta Graph API v21.0)**:
  - Publicación automatizada de fotos y copy en Fan Pages de Facebook usando Page Access Tokens.
- **Programador de Tareas Autónomo (APScheduler)**:
  - Configuración de hora exacta de inicio en zona horaria `America/Bogota`.
  - Publicaciones recurrentes cada hora en el minuto 0 (`:00`) y publicación final de cierre al culminar la competencia.
- **Generador de Descripciones Inteligente**:
  - Estadísticas en tiempo real: número de envíos, equipos con problemas resueltos y agradecimiento al operador.

---

### 5. `nginx` (Puerto `8001`)
Proxy inverso y API Gateway configurado para unificar los microservicios:
- `/facebook-table/publisher/` ➡️ `ms4-publisher:8000`
- `/boca-scraper/` ➡️ `boca-scraper:3001`
- `/generarglobos/` ➡️ `generarglobos:5000`
- `/generartabla/` ➡️ `generartabla:5002`

---

## 💡 Funcionalidades Principales e Innovaciones

1. **Gestión 100% desde el Frontend**:
   - Cambiar de competencia (ej: de `2026/06` a `2027/07`) solo requiere actualizar el año y número de contest en la pantalla de **Configuración**. No requiere reiniciar contenedores ni modificar código.
2. **Sincronización Incondicional de Colores**:
   - Cada publicación refresca los colores en tiempo real y sobreescribe los archivos PNG en disco, asegurando que cualquier cambio de color en BOCA se refleje de inmediato en la siguiente imagen.
3. **Inicio Programado a Hora Exacta**:
   - Permite fijar con precisión cuándo debe iniciar la transmisión del scoreboard sin necesidad de intervención manual durante el inicio de la competencia.
4. **Renderizado Ligero en Servidor**:
   - Generación gráfica rápida y nítida sin depender de navegadores pesados (Chromium/Selenium).

---

## 📦 Requisitos Previos

- **Docker** (versión 20.10 o superior) y **Docker Compose**.
- Cuenta de desarrollador en **Google Cloud Console** (para OAuth2).
- Página de Facebook (Fan Page) y **Page Access Token** de Meta for Developers.

---

## ⚙️ Variables de Entorno (.env)

Crea un archivo `.env` en la raíz del proyecto basándote en la siguiente plantilla de ejemplo:

```env
# ==========================================
# 1. AUTENTICACIÓN GOOGLE (OAuth 2.0)
# ==========================================
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-domain.com/facebook-table/publisher/login/google/callback

# Whitelist de correos permitidos (separados por comas o dominios completos ej: user@email.com,@university.edu)
ALLOWED_EMAILS=

# ==========================================
# 2. SEGURIDAD Y DOMINIOS (Django)
# ==========================================
MS4_SECRET_KEY=your-custom-django-secret-key
CSRF_TRUSTED_ORIGINS=https://your-domain.com,http://your-domain.com

# ==========================================
# 3. BASE DE DATOS BOCA (Opcional)
# ==========================================
# Si se deja vacío, el sistema usará web scraping automático
BOCA_DB_HOST=
BOCA_DB_PORT=5432
BOCA_DB_NAME=bkboca
BOCA_DB_USER=postgres
BOCA_DB_PASS=your-db-password
BOCA_CONTEST_NUMBER=
```


---

## 🚀 Instalación y Despliegue con Docker

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/TheRealOneAle/rpc_autamitazion.git
   cd rpc_autamitazion
   ```

2. **Configurar el archivo `.env`**:
   Completa las credenciales de Google OAuth y el `GOOGLE_REDIRECT_URI` correspondiente a tu dominio o IP.

3. **Construir y levantar todos los microservicios**:
   ```bash
   docker compose up -d --build
   ```

4. **Verificar que todos los contenedores estén activos**:
   ```bash
   docker compose ps
   ```

5. **Acceder a la aplicación**:
   - En desarrollo local: `http://localhost:8001/facebook-table/publisher/`
   - En producción: `https://redprogramacioncompetitiva.com/facebook-table/publisher/`

---

## 🖥️ Guía de Uso del Panel Web

### 1. Inicio de Sesión
- Haz clic en **"Iniciar sesión con Google"**.
- El primer usuario que inicie sesión quedará registrado automáticamente como administrador.

### 2. Configuración Inicial (Pantalla `/configuracion/`)
- **Token de Facebook**:
  1. Ve a [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/).
  2. Selecciona tu **Fan Page** en *User or Page*.
  3. Agrega los permisos `pages_manage_posts`, `pages_read_engagement` y `pages_show_list`.
  4. Genera el Token de Página, cópialo junto con el **Page ID** numérico y guárdalos en el panel.
- **Datos de la Competencia**:
  - Ingresa el **Nombre de la competencia** (ej: `RPC 06 2026`), el **Año** (`2026`) y el **Número de contest** (`06` o `6`).
  - Haz clic en **"Guardar datos del contest"**.

### 3. Dashboard Principal (`/`)
- **Vista Previa en Vivo**: Muestra la imagen generada del Top 10 con los datos actuales y el texto que se publicará.
- **Publicar Ahora**: Dispara un ciclo inmediato de renderizado y publicación en Facebook.
- **Programar Inicio**: Selecciona la fecha y hora exacta en la que comenzará el concurso; el sistema publicará automáticamente la primera tabla y continuará cada hora hasta el cierre.
- **Detener / Reanudar**: Pausa o reactiva las publicaciones programadas en cualquier momento.

---

## 📂 Estructura del Proyecto

```
rpc_autamitazion/
├── boca-scraper/             # Microservicio 1: Extracción BOCA (DB + Scraping)
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── generarglobos/            # Microservicio 2: Generador de globos PNG
│   ├── app.py
│   ├── generarglobos.py
│   ├── bigballoon.png
│   ├── bigballoontransp.png
│   ├── Dockerfile
│   └── requirements.txt
├── generartabla/             # Microservicio 3: Renderizador visual Top 10 (WeasyPrint)
│   ├── app.py
│   ├── flags/                # Banderas SVG de países latinoamericanos
│   ├── logorpc/              # Logo oficial RPC
│   ├── Dockerfile
│   └── requirements.txt
├── ms4-publisher/            # Microservicio 4: Panel Django, Scheduler y Facebook
│   ├── config/               # Configuración Django (settings, urls, wsgi)
│   ├── publisher/            # Aplicación Django (models, views, orchestrator, scheduler)
│   │   ├── templates/        # Plantillas HTML (dashboard.html, config.html, login.html)
│   │   └── migrations/       # Migraciones de base de datos
│   ├── entrypoint.sh
│   ├── Dockerfile
│   └── requirements.txt
├── deploy/                   # Configuraciones de despliegue Nginx
│   └── nginx-compose.conf
├── docker-compose.yml        # Orquestación de contenedores
├── .env                      # Variables de entorno
└── README.md                 # Documentación oficial del proyecto
```

---

## 🔧 Solución de Problemas Comunes

### 1. `Error de Facebook API [200]: (#200) The permission(s) publish_actions are not available`
- **Causa**: Se introdujo un token de usuario personal en lugar de un **Token de Página (Page Access Token)**.
- **Solución**: En el Graph API Explorer de Facebook, selecciona la **Página** en el menú desplegable y asegúrate de otorgar el permiso `pages_manage_posts`.

### 2. `Error 400: redirect_uri_mismatch` en Google OAuth
- **Causa**: La URL en `GOOGLE_REDIRECT_URI` del `.env` no coincide exactamente con las autorizadas en Google Cloud Console.
- **Solución**: En [Google Cloud Console -> Credenciales](https://console.cloud.google.com/apis/credentials), agrega la URL exacta (ej: `https://your-domain.com/facebook-table/publisher/login/google/callback`) en *URIs de redireccionamiento autorizados*.

### 3. `CSRF Failed: Origin checking failed`
- **Causa**: El dominio desde el que accedes no está en `CSRF_TRUSTED_ORIGINS`.
- **Solución**: Añade tu dominio (ej: `https://your-domain.com`) en la variable `CSRF_TRUSTED_ORIGINS` en el archivo `.env` y reinicia el servicio `ms4-publisher`.


---

## 👥 Créditos y Autores

Proyecto desarrollado para la **Red de Programación Competitiva (RPC)** por miembros del **Semillero de Programación Competitiva SILUX** de la **Universidad Francisco de Paula Santander (UFPS)**:

- 💻 **Alejandro Ovallos Torrado**
- 💻 **Jesús Gabriel Torres Daza**
- 💻 **Emerson Amir Vera González**

📌 Repositorio oficial: [TheRealOneAle/rpc_autamitazion](https://github.com/TheRealOneAle/rpc_autamitazion)

