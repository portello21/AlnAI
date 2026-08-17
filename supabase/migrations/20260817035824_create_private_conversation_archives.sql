create table if not exists public.conversation_archives (
  id text primary key,
  profile text not null,
  agent_id text not null,
  title text not null check (char_length(title) between 1 and 120),
  messages jsonb not null default '[]'::jsonb,
  archived_at timestamptz not null default now()
);

alter table public.conversation_archives enable row level security;
alter table public.conversation_archives force row level security;
revoke all on table public.conversation_archives from public, anon, authenticated;
grant select, insert, update, delete on table public.conversation_archives to service_role;

create index if not exists conversation_archives_profile_agent_time_idx
  on public.conversation_archives (profile, agent_id, archived_at desc);
