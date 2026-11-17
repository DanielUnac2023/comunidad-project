import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { supabase, imagenUrl, ETIQUETA, waLink, SITE, type Oferta } from "@/lib/supabase";

export const revalidate = 60;

async function cargar(id: string): Promise<Oferta | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const { data } = await supabase.from("ofertas")
    .select("id,categoria,titulo,descripcion,precio,telefono,imagen_path,aprobada_en,expira_en")
    .eq("id", id).eq("estado", "aprobado").gt("expira_en", new Date().toISOString()).maybeSingle();
  return data as Oferta | null;
}

// Metadatos OpenGraph dinámicos: WhatsApp muestra foto + título al compartir el enlace.
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const o = await cargar(params.id);
  if (!o) return { title: "Oferta no disponible" };
  const desc = [o.precio, o.descripcion].filter(Boolean).join(" · ").slice(0, 160);
  const img = imagenUrl(o.imagen_path);
  return {
    title: o.titulo,
    description: desc,
    alternates: { canonical: `${SITE}/oferta/${o.id}` },
    openGraph: {
      type: "article", title: o.titulo, description: desc, url: `${SITE}/oferta/${o.id}`,
      images: img ? [{ url: img, width: 1200, height: 900, alt: o.titulo }] : [],
    },
    twitter: { card: img ? "summary_large_image" : "summary", title: o.titulo, description: desc, images: img ? [img] : [] },
  };
}

export default async function OfertaPage({ params }: { params: { id: string } }) {
  const o = await cargar(params.id);
  if (!o) notFound();
  const img = imagenUrl(o.imagen_path);
  const vence = new Date(o.expira_en).toLocaleDateString("es", { day: "numeric", month: "long" });
  return (
    <article className="detalle">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {img && <img src={img} alt={o.titulo} />}
      <div>
        <span className={`tag ${o.categoria}`}>{ETIQUETA[o.categoria]}</span>
        <h1>{o.titulo}</h1>
        <p className="desc">{o.descripcion}</p>
        {o.precio && <p className="precio">{o.precio}</p>}
        <a className="btn grande" href={waLink(o)} target="_blank" rel="noopener noreferrer">Contactar por WhatsApp</a>
        <p className="nota">Publicada tras revisión. Disponible hasta el {vence}. Verifica siempre los detalles con el anunciante antes de pagar.</p>
      </div>
    </article>
  );
}
