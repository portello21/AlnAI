create table if not exists public.response_feedback (
  id uuid primary key default gen_random_uuid(),
  profile text not null,
  agent_id text not null,
  message_hash text not null check (char_length(message_hash) = 64),
  rating smallint not null check (rating in (-1, 1)),
  reason text null check (reason is null or char_length(reason) <= 240),
  provider text null,
  model text null,
  created_at timestamptz not null default now(),
  unique (profile, agent_id, message_hash)
);

alter table public.response_feedback enable row level security;
alter table public.response_feedback force row level security;
revoke all on table public.response_feedback from public, anon, authenticated;
grant select, insert, update, delete on table public.response_feedback to service_role;

create index if not exists response_feedback_profile_created_idx
  on public.response_feedback (profile, created_at desc);
