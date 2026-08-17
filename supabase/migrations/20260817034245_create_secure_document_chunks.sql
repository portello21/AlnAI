create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  namespace text not null,
  profile text not null,
  agent_id text not null,
  file_hash text not null,
  filename text not null,
  mime_type text not null default 'unknown',
  content text not null,
  chunk_index integer not null check (chunk_index >= 0),
  chunk_count integer not null check (chunk_count > 0 and chunk_index < chunk_count),
  embedding extensions.vector(384) not null,
  content_tsv tsvector generated always as (to_tsvector('simple', content)) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (namespace, file_hash, chunk_index)
);

alter table public.document_chunks enable row level security;
alter table public.document_chunks force row level security;
revoke all on table public.document_chunks from public, anon, authenticated;
grant select, insert, update, delete on table public.document_chunks to service_role;

create index if not exists document_chunks_namespace_file_idx
  on public.document_chunks (namespace, file_hash);
create index if not exists document_chunks_content_tsv_idx
  on public.document_chunks using gin (content_tsv);
create index if not exists document_chunks_embedding_hnsw_idx
  on public.document_chunks using hnsw (embedding vector_cosine_ops);
