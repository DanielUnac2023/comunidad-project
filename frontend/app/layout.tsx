import type { Metadata } from "next";
import Link from "next/link";
import { Bricolage_Grotesque, Source_Sans_3 } from "next/font/google";
import "./globals.css";

const titulo = Bricolage_Grotesque({ subsets: ["latin"], variable: "--f-titulo", weight: ["700", "800"] });
const cuerpo = Source_Sans_3({ subsets: ["latin"], variable: "--f-cuerpo" });

const site = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
export const metadata: Metadata = {
  metadataBase: new URL(site),
  title: { default: "Ofertas de la comunidad", template: "%s · Ofertas de la comunidad" },
  description: "Productos, servicios y empleos publicados por los miembros de la comunidad.",
  openGraph: { type: "website", siteName: "Ofertas de la comunidad", locale: "es_ES" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${titulo.variable} ${cuerpo.variable}`}>
      <body>
        <header className="top">
          <div className="wrap">
            <Link href="/" className="marca">Ofertas de la comunidad</Link>
            <Link href="/publicar" className="btn sec">Publicar una oferta</Link>
          </div>
        </header>
        <main className="wrap">{children}</main>
      </body>
    </html>
  );
}
