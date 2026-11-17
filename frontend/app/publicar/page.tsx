"use client";
import { useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL!;

export default function Publicar() {
  const [estado, setEstado] = useState<"idle" | "enviando" | "ok" | "error">("idle");
  const [error, setError] = useState("");

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setEstado("enviando"); setError("");
    try {
      const r = await fetch(`${BACKEND}/api/ofertas`, { method: "POST", body: new FormData(e.currentTarget) });
      if (!r.ok) { setError((await r.json().catch(() => ({}))).detail ?? "No se pudo enviar."); return setEstado("error"); }
      setEstado("ok");
    } catch { setError("No hay conexión con el servidor. Intenta de nuevo."); setEstado("error"); }
  }

  if (estado === "ok") return (
    <div className="msg" style={{ margin: "32px 0" }}>
      <h2>Recibimos tu oferta</h2>
      <p>Un administrador la revisará. Cuando se apruebe estará en el catálogo durante 30 días.</p>
    </div>
  );

  return (
    <>
      <section className="intro"><h1>Publica tu oferta</h1>
        <p>Es gratis. Un administrador la revisa antes de que aparezca en el catálogo.</p></section>
      <form className="pub" onSubmit={enviar}>
        <label>Tipo de oferta
          <select name="categoria" required defaultValue="">
            <option value="" disabled>Elige una opción</option>
            <option value="producto">Producto</option><option value="servicio">Servicio</option><option value="empleo">Empleo</option>
          </select></label>
        <label>Título <input type="text" name="titulo" required minLength={3} maxLength={120} /></label>
        <label>Descripción <textarea name="descripcion" required minLength={5} maxLength={2000} /></label>
        <label>Precio <small>Opcional. Ejemplo: $50.000 o «a convenir»</small><input type="text" name="precio" maxLength={60} /></label>
        <label>Teléfono de WhatsApp <small>Con código de país, solo números. Ejemplo: 573001234567</small>
          <input type="tel" name="telefono" required inputMode="numeric" pattern="[0-9 +()-]{8,20}" /></label>
        <label>Foto <small>Opcional. Una imagen, máximo 8 MB.</small><input type="file" name="imagen" accept="image/*" /></label>
        <input className="oculto" type="text" name="web_url" tabIndex={-1} autoComplete="off" aria-hidden="true" />
        {estado === "error" && <p className="msg error" role="alert">{error}</p>}
        <button className="btn grande" type="submit" disabled={estado === "enviando"}>
          {estado === "enviando" ? "Enviando… puede tardar hasta un minuto" : "Enviar para revisión"}
        </button>
      </form>
    </>
  );
}
