-- ============ EXTENSIONES ============
create extension if not exists pgcrypto;
create extension if not exists pg_cron;      -- si falla: Database > Extensions > activar pg_cron

-- ============ TIPOS ============
do $$ begin
  create type categoria_oferta as enum ('producto','servicio','empleo');
exception when duplicate_object then null; end $$;
do $$ begin
  create type estado_oferta as enum ('pendiente','aprobado','rechazado','caducado');
exception when duplicate_object then null; end $$;

-- ============ TABLA ============
create table if not exists public.ofertas (
  id               uuid primary key default gen_random_uuid(),
  categoria        categoria_oferta not null,
  titulo           text not null check (char_length(titulo) between 3 and 120),
  descripcion      text not null check (char_length(descripcion) between 5 and 2000),
  precio           text,
  telefono         text not null check (telefono ~ '^[0-9]{8,15}$'),
  imagen_path      text,                       -- ruta dentro del bucket 'ofertas'
  estado           estado_oferta not null default 'pendiente',
  origen           text not null default 'whatsapp' check (origen in ('whatsapp','web')),
  wa_message_id    text unique,                -- evita duplicados por reintentos de Meta
  wa_user          text,                       -- número que escribió al bot (para responderle)
  creada_en        timestamptz not null default now(),
  aprobada_en      timestamptz,
  expira_en        timestamptz,                -- se fija al aprobar (+30 días)
  busqueda         tsvector generated always as (
                     to_tsvector('spanish', coalesce(titulo,'')||' '||coalesce(descripcion,''))
                   ) stored
);
create index if not exists ofertas_busqueda_idx on public.ofertas using gin (busqueda);
create index if not exists ofertas_listado_idx  on public.ofertas (estado, categoria, aprobada_en desc);

-- ============ RLS ============
alter table public.ofertas enable row level security;

-- Público (anon): solo lectura de ofertas aprobadas y vigentes.
drop policy if exists "publico lee aprobadas" on public.ofertas;
create policy "publico lee aprobadas" on public.ofertas
  for select to anon, authenticated
  using (estado = 'aprobado' and expira_en > now());

-- Sin políticas de insert/update/delete para anon: todo lo escribe el backend con la
-- service_role key (que se salta RLS). Nadie puede publicar sin pasar por moderación.

-- ============ STORAGE ============
insert into storage.buckets (id, name, public) values ('ofertas','ofertas', true)
on conflict (id) do nothing;

drop policy if exists "lectura publica imagenes" on storage.objects;
create policy "lectura publica imagenes" on storage.objects
  for select to anon, authenticated using (bucket_id = 'ofertas');

-- ============ CADUCIDAD ============
-- Marca como caducadas las aprobadas vencidas. El borrado real de imágenes y filas viejas
-- lo hace el backend (/cron/limpieza): borrar filas de storage.objects por SQL NO elimina
-- el archivo físico.
create or replace function public.marcar_caducadas() returns void
language sql security definer set search_path = public as $$
  update public.ofertas set estado = 'caducado'
  where estado = 'aprobado' and expira_en <= now();
$$;

select cron.schedule('marcar-caducadas', '15 * * * *', $$select public.marcar_caducadas()$$);
