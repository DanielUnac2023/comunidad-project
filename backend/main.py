"""Backend: webhook WhatsApp Cloud API + bot de Telegram + Supabase (FastAPI)."""
import asyncio, hashlib, hmac, io, os, re, time, uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from PIL import Image
from supabase import create_client

E = os.environ
sb = create_client(E["SUPABASE_URL"], E["SUPABASE_SERVICE_KEY"])
BUCKET = "ofertas"
WEBAPP = E["PUBLIC_WEBAPP_URL"].rstrip("/")
STORAGE_BASE = E["STORAGE_PUBLIC_BASE"].rstrip("/")
GRAPH = "https://graph.facebook.com/v21.0"
TG = f"https://api.telegram.org/bot{E['TG_BOT_TOKEN']}"
ADMIN_IDS = {int(x) for x in E["TG_ADMIN_IDS"].split(",") if x.strip()}
DIAS_VIGENCIA = 30
CATS = {"producto": "producto", "productos": "producto", "servicio": "servicio",
        "servicios": "servicio", "empleo": "empleo", "empleos": "empleo", "trabajo": "empleo"}
EMOJI = {"producto": "🛍️", "servicio": "🛠️", "empleo": "💼"}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=[WEBAPP], allow_methods=["POST"], allow_headers=["*"])
http = httpx.AsyncClient(timeout=30)

PLANTILLA = (
    "¡Hola! 👋 Para publicar tu oferta envíame *un solo mensaje* con este formato "
    "(puedes adjuntar 1 foto y escribirlo en el pie de foto):\n\n"
    "Categoría: producto / servicio / empleo\n"
    "Título: \n"
    "Descripción: \n"
    "Precio: \n"
    "Teléfono: \n\n"
    "Un administrador la revisará y te avisaremos."
)

# ------------------------------------------------------------------ utilidades
def solo_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def parsear(texto: str) -> dict:
    """Lee líneas 'Campo: valor'. La descripción puede ocupar varias líneas."""
    claves = {"categoria": "categoria", "categoría": "categoria", "titulo": "titulo", "título": "titulo",
              "descripcion": "descripcion", "descripción": "descripcion", "precio": "precio",
              "telefono": "telefono", "teléfono": "telefono", "contacto": "telefono"}
    campos, actual = {}, None
    for linea in texto.splitlines():
        m = re.match(r"^\s*([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\s*:\s*(.*)$", linea)
        if m and m.group(1).lower() in claves:
            actual = claves[m.group(1).lower()]
            campos[actual] = m.group(2).strip()
        elif actual:
            campos[actual] += "\n" + linea.strip()
    return {k: v.strip() for k, v in campos.items()}

def validar(c: dict, tel_defecto: str):
    cat = CATS.get(c.get("categoria", "").lower().strip())
    tel = solo_digitos(c.get("telefono", "")) or solo_digitos(tel_defecto)
    if not cat: return None, "La categoría debe ser producto, servicio o empleo."
    if len(c.get("titulo", "")) < 3: return None, "Falta el título."
    if len(c.get("descripcion", "")) < 5: return None, "Falta la descripción."
    if not re.fullmatch(r"\d{8,15}", tel): return None, "El teléfono debe incluir código de país (solo números)."
    return {"categoria": cat, "titulo": c["titulo"][:120], "descripcion": c["descripcion"][:2000],
            "precio": c.get("precio") or None, "telefono": tel}, None

def comprimir(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((1200, 1200))
    out = io.BytesIO(); img.save(out, "JPEG", quality=78, optimize=True)
    return out.getvalue()

def subir_imagen(data: bytes) -> str:
    path = f"{datetime.now(timezone.utc):%Y/%m}/{uuid.uuid4().hex}.jpg"
    sb.storage.from_(BUCKET).upload(path, comprimir(data), {"content-type": "image/jpeg"})
    return path

def borrar_imagen(path):
    if path:
        try: sb.storage.from_(BUCKET).remove([path])
        except Exception as e: print("no se pudo borrar", path, e)

def texto_oferta(o: dict) -> str:
    precio = f"\nPrecio: {o['precio']}" if o.get("precio") else ""
    return (f"{EMOJI[o['categoria']]} {o['categoria'].upper()}\n{o['titulo']}\n\n{o['descripcion']}{precio}\n"
            f"Contacto: +{o['telefono']}\nOrigen: {o['origen']}")

def mensaje_difusion(o: dict) -> str:
    """Texto listo para reenviar al grupo de WhatsApp (usa *negrita* de WhatsApp)."""
    precio = f"💰 {o['precio']}\n" if o.get("precio") else ""
    return (f"{EMOJI[o['categoria']]} *{o['titulo']}*\n\n{o['descripcion']}\n\n{precio}"
            f"📲 Escríbele: https://wa.me/{o['telefono']}\n"
            f"🔎 Foto y más ofertas: {WEBAPP}/oferta/{o['id']}")

# ------------------------------------------------------------------ Telegram
async def tg(method: str, **payload):
    r = await http.post(f"{TG}/{method}", json=payload)
    if r.status_code >= 400: print("Telegram error", r.text)
    return r

async def notificar_admins(o: dict):
    teclado = {"inline_keyboard": [[{"text": "✅ Aprobar", "callback_data": f"a:{o['id']}"},
                                    {"text": "❌ Rechazar", "callback_data": f"r:{o['id']}"}]]}
    chat = int(E["TG_ADMIN_CHAT_ID"])
    if o.get("imagen_path"):
        await tg("sendPhoto", chat_id=chat, photo=f"{STORAGE_BASE}/{o['imagen_path']}",
                 caption=texto_oferta(o)[:1024], reply_markup=teclado)
    else:
        await tg("sendMessage", chat_id=chat, text=texto_oferta(o), reply_markup=teclado)

@app.post("/telegram/webhook")
async def telegram_webhook(req: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    if x_telegram_bot_api_secret_token != E["TG_WEBHOOK_SECRET"]:
        raise HTTPException(403)
    cb = (await req.json()).get("callback_query")
    if not cb: return {"ok": True}
    if cb["from"]["id"] not in ADMIN_IDS:
        await tg("answerCallbackQuery", callback_query_id=cb["id"], text="No autorizado", show_alert=True)
        return {"ok": True}
    accion, oid = cb["data"].split(":", 1)
    msg = cb["message"]
    # UPDATE condicionado a 'pendiente': si el otro admin ya decidió, no hace nada.
    if accion == "a":
        ahora = datetime.now(timezone.utc)
        cambios = {"estado": "aprobado", "aprobada_en": ahora.isoformat(),
                   "expira_en": (ahora + timedelta(days=DIAS_VIGENCIA)).isoformat()}
    else:
        cambios = {"estado": "rechazado"}
    res = await asyncio.to_thread(lambda: sb.table("ofertas").update(cambios)
                                  .eq("id", oid).eq("estado", "pendiente").execute())
    if not res.data:
        await tg("answerCallbackQuery", callback_query_id=cb["id"], text="Ya fue procesada.")
        return {"ok": True}
    o = res.data[0]
    marca = "✅ APROBADA" if accion == "a" else "❌ RECHAZADA"
    con_foto = bool(msg.get("photo"))
    await tg("editMessageCaption" if con_foto else "editMessageText",
             chat_id=msg["chat"]["id"], message_id=msg["message_id"],
             **{("caption" if con_foto else "text"):
                f"{marca} por {cb['from'].get('first_name', 'admin')}\n\n{texto_oferta(o)}"[:1024]})
    await tg("answerCallbackQuery", callback_query_id=cb["id"], text=marca)
    if accion == "a":
        # Mensaje listo para "Reenviar" al grupo de WhatsApp (texto plano, sin parse_mode)
        await tg("sendMessage", chat_id=msg["chat"]["id"], text=mensaje_difusion(o))
        if o.get("wa_user"):
            await wa_texto(o["wa_user"], f"✅ Tu oferta «{o['titulo']}» fue aprobada: {WEBAPP}/oferta/{o['id']}")
    else:
        await asyncio.to_thread(borrar_imagen, o.get("imagen_path"))
        await asyncio.to_thread(lambda: sb.table("ofertas").update({"imagen_path": None}).eq("id", oid).execute())
        if o.get("wa_user"):
            await wa_texto(o["wa_user"], f"Tu oferta «{o['titulo']}» no fue aprobada. Puedes corregirla y enviarla otra vez.")
    return {"ok": True}

# ------------------------------------------------------------------ WhatsApp
async def wa_texto(a: str, texto: str):
    # Gratis dentro de las 24 h posteriores al último mensaje del usuario.
    # Pasada la ventana, Meta rechaza el envío: solo se registra el error.
    r = await http.post(f"{GRAPH}/{E['WA_PHONE_ID']}/messages",
                        headers={"Authorization": f"Bearer {E['WA_TOKEN']}"},
                        json={"messaging_product": "whatsapp", "to": a, "type": "text", "text": {"body": texto}})
    if r.status_code >= 400: print("WA error", r.text)

async def wa_descargar_media(media_id: str) -> bytes:
    h = {"Authorization": f"Bearer {E['WA_TOKEN']}"}
    meta = (await http.get(f"{GRAPH}/{media_id}", headers=h)).json()
    return (await http.get(meta["url"], headers=h)).content

@app.get("/whatsapp/webhook")
async def wa_verificar(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == E["WA_VERIFY_TOKEN"]:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403)

async def procesar_mensaje(m: dict):
    de = m["from"]
    if m["type"] == "image": texto, media = m["image"].get("caption", ""), m["image"]["id"]
    elif m["type"] == "text": texto, media = m["text"]["body"], None
    else: return await wa_texto(de, "Solo puedo leer texto o una foto con pie de foto.\n\n" + PLANTILLA)
    campos = parsear(texto)
    if not campos: return await wa_texto(de, PLANTILLA)
    datos, error = validar(campos, de)
    if error: return await wa_texto(de, f"⚠️ {error}\n\n{PLANTILLA}")
    ruta = None
    if media:
        try: ruta = await asyncio.to_thread(subir_imagen, await wa_descargar_media(media))
        except Exception as e: print("imagen falló", e)
    fila = {**datos, "imagen_path": ruta, "origen": "whatsapp", "wa_message_id": m["id"], "wa_user": de}
    try:
        res = await asyncio.to_thread(lambda: sb.table("ofertas").insert(fila).execute())
    except Exception as e:                       # wa_message_id repetido = reintento de Meta
        print("insert:", e); return
    await notificar_admins(res.data[0])
    await wa_texto(de, "✅ ¡Recibido! Tu oferta está en revisión. Te avisaremos cuando se publique.")

@app.post("/whatsapp/webhook")
async def wa_recibir(req: Request, x_hub_signature_256: str = Header(None)):
    cuerpo = await req.body()
    esperado = "sha256=" + hmac.new(E["WA_APP_SECRET"].encode(), cuerpo, hashlib.sha256).hexdigest()
    if not x_hub_signature_256 or not hmac.compare_digest(esperado, x_hub_signature_256):
        raise HTTPException(403)
    for entry in (await req.json()).get("entry", []):
        for ch in entry.get("changes", []):
            for m in ch.get("value", {}).get("messages", []):
                asyncio.create_task(procesar_mensaje(m))   # responde 200 rápido a Meta
    return {"ok": True}

# ------------------------------------------------------------------ Formulario web
_visitas = defaultdict(list)

@app.post("/api/ofertas")
async def publicar_web(request: Request, categoria: str = Form(...), titulo: str = Form(...),
                       descripcion: str = Form(...), precio: str = Form(""), telefono: str = Form(...),
                       web_url: str = Form(""),                # honeypot: humanos lo dejan vacío
                       imagen: UploadFile | None = File(None)):
    if web_url: return {"ok": True}                            # bot: se finge éxito
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    ahora = time.time(); _visitas[ip] = [t for t in _visitas[ip] if ahora - t < 3600]
    if len(_visitas[ip]) >= 5: raise HTTPException(429, "Demasiados envíos. Intenta más tarde.")
    _visitas[ip].append(ahora)
    datos, error = validar({"categoria": categoria, "titulo": titulo, "descripcion": descripcion,
                            "precio": precio, "telefono": telefono}, "")
    if error: raise HTTPException(422, error)
    ruta = None
    if imagen and imagen.filename:
        raw = await imagen.read()
        if len(raw) > 8_000_000: raise HTTPException(413, "La imagen supera 8 MB.")
        try: ruta = await asyncio.to_thread(subir_imagen, raw)
        except Exception: raise HTTPException(422, "Imagen no válida.")
    res = await asyncio.to_thread(lambda: sb.table("ofertas").insert(
        {**datos, "imagen_path": ruta, "origen": "web"}).execute())
    await notificar_admins(res.data[0])
    return {"ok": True}

# ------------------------------------------------------------------ Mantenimiento
@app.get("/health")
async def health(): return {"ok": True}

@app.post("/cron/limpieza")
async def limpieza(x_cron_secret: str = Header(None)):
    if x_cron_secret != E["CRON_SECRET"]: raise HTTPException(403)
    ahora = datetime.now(timezone.utc).isoformat()
    sb.table("ofertas").update({"estado": "caducado"}).eq("estado", "aprobado").lte("expira_en", ahora).execute()
    # 1) borrar imágenes de ofertas caducadas o rechazadas
    venc = sb.table("ofertas").select("id,imagen_path").not_.is_("imagen_path", "null") \
             .in_("estado", ["caducado", "rechazado"]).execute().data
    for o in venc:
        borrar_imagen(o["imagen_path"])
        sb.table("ofertas").update({"imagen_path": None}).eq("id", o["id"]).execute()
    # 2) pendientes olvidadas > 7 días: se eliminan con su imagen
    viejo = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    for o in sb.table("ofertas").select("id,imagen_path").eq("estado", "pendiente").lte("creada_en", viejo).execute().data:
        borrar_imagen(o["imagen_path"]); sb.table("ofertas").delete().eq("id", o["id"]).execute()
    # 3) filas caducadas/rechazadas > 90 días: borrado definitivo
    corte = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    sb.table("ofertas").delete().in_("estado", ["caducado", "rechazado"]).lte("creada_en", corte).execute()
    return {"ok": True, "imagenes_borradas": len(venc)}
