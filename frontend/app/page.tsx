import Link from "next/link";
import { supabase, imagenUrl, ETIQUETA, type Oferta, type Categoria } from "@/lib/supabase";

export const revalidate = 0; // lista siempre fresca (usa searchParams)

const CATS: (Categoria | "")[] = ["", "producto", "servicio", "empleo"];
const COLOR: Record<Categoria, string> = { producto: "var(--producto)", servicio: "var(--servicio)", empleo: "var(--empleo)" };

export default async function Home({ searchParams }: { searchParams: { q?: string; cat?: string } }) {
  const q = (searchParams.q ?? "").trim().slice(0, 80);
  const cat = CATS.includes((searchParams.cat ?? "") as Categoria) ? (searchParams.cat ?? "") : "";

  let query = supabase.from("ofertas")
    .select("id,categoria,titulo,descripcion,precio,telefono,imagen_path,aprobada_en,expira_en")
    .eq("estado", "aprobado").gt("expira_en", new Date().toISOString())
    .order("aprobada_en", { ascending: false }).limit(60);
  if (cat) query = query.eq("categoria", cat);
  if (q) query = query.textSearch("busqueda", q, { config: "spanish", type: "websearch" });
  const { data } = await query;
  const ofertas = (data ?? []) as Oferta[];

  const href = (c: string) => `/?${new URLSearchParams({ ...(q && { q }), ...(c && { cat: c }) })}`;

  return (
    <>
      <section className="intro">
        <h1>Lo que ofrece la comunidad, en un solo lugar</h1>
        <p>Cada oferta se revisa antes de publicarse y dura 30 días. Escribe directo al anunciante por WhatsApp.</p>
      </section>

      <form className="filtros" role="search" action="/">
        <input type="search" name="q" defaultValue={q} placeholder="Buscar: bicicleta, plomero, cocinero…" aria-label="Buscar ofertas" />
        {cat && <input type="hidden" name="cat" value={cat} />}
        <button className="btn" type="submit">Buscar</button>
      </form>
      <nav className="chips" aria-label="Categorías" style={{ marginBottom: 20 }}>
        {CATS.map((c) => (
          <Link key={c || "todas"} href={href(c)} className="chip" aria-current={cat === c}>
            {c ? ETIQUETA[c] + "s" : "Todas"}
          </Link>
        ))}
      </nav>

      {ofertas.length === 0 ? (
        <p className="vacio">No hay ofertas {q || cat ? "con esos filtros" : "publicadas todavía"}. <Link href="/publicar">Publica la primera</Link>.</p>
      ) : (
        <div className="grid">
          {ofertas.map((o) => {
            const img = imagenUrl(o.imagen_path);
            return (
              <Link key={o.id} href={`/oferta/${o.id}`} className="card">
                {img
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <img className="foto" src={img} alt="" loading="lazy" />
                  : <div className="sin-foto" style={{ background: COLOR[o.categoria] }}>{ETIQUETA[o.categoria]}</div>}
                <div className="cuerpo">
                  <span className={`tag ${o.categoria}`}>{ETIQUETA[o.categoria]}</span>
                  <h3>{o.titulo}</h3>
                  {o.precio && <span className="precio">{o.precio}</span>}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
