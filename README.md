# Ofertas de la comunidad — bot + moderación + WebApp ($0/mes)

```
Usuario ─WhatsApp─▶ Meta Cloud API ─▶ FastAPI (Render) ─▶ Supabase (BD + Storage)
Usuario ─Web (/publicar)──────────────▶      │
                                             ▼
                              Telegram (grupo admins) [✅ Aprobar] [❌ Rechazar]
                                             ▼ (aprobar)
                        mensaje listo → admin "Reenviar" → grupo WhatsApp
                        WebApp (Vercel) lee solo ofertas aprobadas y vigentes
```

## Estructura
```
supabase/schema.sql          tablas, RLS, bucket, función + pg_cron
backend/main.py              webhooks WhatsApp y Telegram, formulario web, limpieza
backend/render.yaml          despliegue en Render (plan free)
frontend/                    Next.js 14 (catálogo, /oferta/[id] con OpenGraph, /publicar)
.github/workflows/           limpieza diaria gratis (GitHub Actions)
```

## 1. Supabase
1. Crea un proyecto en supabase.com (plan Free).
2. SQL Editor → pega y ejecuta `supabase/schema.sql`. Si `pg_cron` da error, actívalo en *Database → Extensions* y vuelve a ejecutar.
3. *Project Settings → API*: copia `Project URL`, la clave **anon** (pública) y la **service_role** (secreta, solo backend).
4. Verifica en *Storage* que existe el bucket público `ofertas`.

## 2. Bot de Telegram
1. En Telegram habla con **@BotFather** → `/newbot` → guarda el token (`TG_BOT_TOKEN`).
2. Crea un grupo con los 2 admins, añade el bot. Escribe cualquier mensaje en el grupo.
3. Abre `https://api.telegram.org/bot<TOKEN>/getUpdates` y anota `chat.id` del grupo (`TG_ADMIN_CHAT_ID`, empieza con `-`) y el `from.id` de cada admin (`TG_ADMIN_IDS`).
4. Más abajo (paso 5) registrarás el webhook.

## 3. WhatsApp Cloud API (Meta)
1. developers.facebook.com → *Crear app* → tipo **Business** → añade el producto **WhatsApp**.
2. *WhatsApp → API Setup*: anota el **Phone number ID** (`WA_PHONE_ID`). Con el número de prueba solo puedes escribir con 5 números verificados: sirve para probar.
3. Token permanente: *Business Settings → Usuarios del sistema* → crea uno (Admin) → asígnale la app → *Generar token* con permisos `whatsapp_business_messaging` y `whatsapp_business_management` (`WA_TOKEN`).
4. *App Settings → Basic*: copia **App Secret** (`WA_APP_SECRET`).
5. Para recibir mensajes de cualquier usuario necesitas registrar un **número real** (que no esté activo en WhatsApp/WhatsApp Business app) y pasar la app a modo **Live**. Meta puede pedir verificación del negocio; revisa los requisitos actuales en su documentación.
6. El webhook se configura en el paso 5 de esta guía.

## 4. Backend en Render
1. Sube este proyecto a un repositorio de GitHub.
2. render.com → *New → Web Service* → el repo → *Root Directory* `backend`, runtime Python, plan **Free**
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. *Environment*: carga todas las variables de `backend/.env.example` con tus valores. `PUBLIC_WEBAPP_URL` la completas tras el paso 6.
   - `STORAGE_PUBLIC_BASE` = `<SUPABASE_URL>/storage/v1/object/public/ofertas`
4. Anota la URL (`https://ofertas-backend.onrender.com`) y comprueba `/health`.

## 5. Conectar los webhooks
- **Telegram** (una vez, en cualquier terminal):
  ```
  curl "https://api.telegram.org/bot<TG_BOT_TOKEN>/setWebhook" \
    -d "url=https://<TU-BACKEND>/telegram/webhook" \
    -d "secret_token=<TG_WEBHOOK_SECRET>" \
    -d 'allowed_updates=["callback_query"]'
  ```
- **WhatsApp**: Meta → WhatsApp → *Configuration* → Webhook: URL `https://<TU-BACKEND>/whatsapp/webhook`, Verify token = `WA_VERIFY_TOKEN`, y suscríbete al campo **messages**.

## 6. Frontend en Vercel
1. vercel.com → *Add New Project* → mismo repo → **Root Directory: `frontend`** (Hobby/gratis).
2. Variables (ver `frontend/.env.example`): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_SITE_URL`.
3. Deploy. Copia la URL final a `PUBLIC_WEBAPP_URL` en Render (y redeploy) y a `NEXT_PUBLIC_SITE_URL` en Vercel.
4. Prueba OpenGraph: pega un enlace `/oferta/<id>` en un chat de WhatsApp; debe mostrar foto y título.

## 7. Mantenimiento automático (gratis)
- GitHub → *Settings → Secrets and variables → Actions*: `BACKEND_URL` (URL de Render) y `CRON_SECRET` (el mismo del backend). El workflow `mantenimiento.yml` corre cada día: caduca ofertas > 30 días, **borra sus imágenes** de Storage y elimina filas viejas. Esto también mantiene activo el proyecto de Supabase.
- Evitar que Render se duerma: crea un monitor gratuito (UptimeRobot o cron-job.org) que llame a `GET /health` cada 10–14 min. Sin esto, el primer mensaje tras inactividad puede tardar ~1 min; Meta reintenta el webhook y el backend ignora duplicados.

## 8. Prueba de punta a punta
1. Escribe al número del bot → recibes la plantilla.
2. Envía el formato (con foto en el pie de foto) → respuesta «en revisión» + mensaje en Telegram con botones.
3. Aprobar → llega el mensaje formateado → «Reenviar» al grupo de WhatsApp; la oferta aparece en la web.
4. Repite desde `/publicar`.

## Límites y puntos a vigilar
- **Ventana de 24 h**: los avisos al anunciante («aprobada/rechazada») solo se entregan gratis si él escribió hace menos de 24 h; si no, Meta los rechaza y el backend lo ignora (no pasa nada grave). No uses plantillas: tienen costo.
- Las capas gratuitas cambian: confirma en las páginas de precios de Supabase, Render, Vercel y Meta. A fecha de hoy (nov 2026) no las he verificado.
- Supabase Free: 500 MB de BD y 1 GB de Storage; las imágenes se comprimen a ≤1200 px (~100–200 KB) y se borran a los 30 días.
- El formulario web tiene honeypot y límite de 5 envíos/hora por IP (en memoria). Si hay spam, añade Cloudflare Turnstile (gratis).
- Nunca expongas la `service_role` en el frontend.
