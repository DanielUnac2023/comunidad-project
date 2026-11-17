import Link from "next/link";
export default function NoEncontrada() {
  return (
    <div className="vacio">
      <h1>Esta oferta ya no está disponible</h1>
      <p>Las ofertas duran 30 días. <Link href="/">Mira las ofertas vigentes</Link>.</p>
    </div>
  );
}
