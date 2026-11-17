import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  { auth: { persistSession: false } }
);

export type Categoria = "producto" | "servicio" | "empleo";
export type Oferta = {
  id: string; categoria: Categoria; titulo: string; descripcion: string;
  precio: string | null; telefono: string; imagen_path: string | null;
  aprobada_en: string; expira_en: string;
};

export const SITE = (process.env.NEXT_PUBLIC_SITE_URL ?? "").replace(/\/$/, "");
export const imagenUrl = (path: string | null) =>
  path ? `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/ofertas/${path}` : null;

export const ETIQUETA: Record<Categoria, string> = { producto: "Producto", servicio: "Servicio", empleo: "Empleo" };
export const waLink = (o: Pick<Oferta, "telefono" | "titulo">) =>
  `https://wa.me/${o.telefono}?text=${encodeURIComponent(`Hola, vi tu anuncio «${o.titulo}» en el catálogo de la comunidad.`)}`;
