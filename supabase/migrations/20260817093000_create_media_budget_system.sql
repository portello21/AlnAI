create table if not exists public.rog_budget_settings (
  id boolean primary key default true check (id),
  monthly_limit_usd numeric(8,2) not null default 10 check (monthly_limit_usd between 0 and 10),
  daily_limit_usd numeric(8,2) not null default 1 check (daily_limit_usd between 0 and 10),
  image_limit_usd numeric(8,2) not null default 2 check (image_limit_usd between 0 and 10),
  video_limit_usd numeric(8,2) not null default 5 check (video_limit_usd between 0 and 10),
  paid_media_enabled boolean not null default false,
  updated_at timestamptz not null default now()
);

create table if not exists public.rog_profile_quotas (
  profile text primary key check (profile in ('allan','beatriz','tainan')),
  monthly_limit_usd numeric(8,2) not null check (monthly_limit_usd between 0 and 10),
  image_enabled boolean not null default true,
  video_enabled boolean not null default false,
  updated_at timestamptz not null default now()
);

create table if not exists public.rog_media_usage (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile text not null check (profile in ('allan','beatriz','tainan')),
  media_type text not null check (media_type in ('image','video')),
  provider text not null,
  model text not null,
  status text not null check (status in ('reserved','completed','failed','cancelled')),
  estimated_cost_usd numeric(8,4) not null check (estimated_cost_usd >= 0),
  actual_cost_usd numeric(8,4) check (actual_cost_usd >= 0),
  prompt_hash text not null,
  storage_path text,
  error_type text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.rog_budget_settings enable row level security;
alter table public.rog_profile_quotas enable row level security;
alter table public.rog_media_usage enable row level security;

revoke all on public.rog_budget_settings, public.rog_profile_quotas, public.rog_media_usage from anon, authenticated;
grant select on public.rog_budget_settings, public.rog_profile_quotas, public.rog_media_usage to authenticated;

drop policy if exists "admin_reads_budget_settings" on public.rog_budget_settings;
create policy "admin_reads_budget_settings" on public.rog_budget_settings for select to authenticated
using (((select auth.jwt()) -> 'app_metadata' ->> 'rog_role') = 'admin');
drop policy if exists "users_read_own_quota" on public.rog_profile_quotas;
create policy "users_read_own_quota" on public.rog_profile_quotas for select to authenticated
using (profile = ((select auth.jwt()) -> 'app_metadata' ->> 'rog_profile') or ((select auth.jwt()) -> 'app_metadata' ->> 'rog_role') = 'admin');
drop policy if exists "users_read_own_media_usage" on public.rog_media_usage;
create policy "users_read_own_media_usage" on public.rog_media_usage for select to authenticated
using ((select auth.uid()) = user_id or ((select auth.jwt()) -> 'app_metadata' ->> 'rog_role') = 'admin');

insert into public.rog_budget_settings (id) values (true) on conflict (id) do nothing;
insert into public.rog_profile_quotas (profile, monthly_limit_usd, image_enabled, video_enabled) values
('allan', 4, true, false), ('beatriz', 3, true, false), ('tainan', 3, true, false)
on conflict (profile) do nothing;

create index if not exists rog_media_usage_budget_idx on public.rog_media_usage (created_at, profile, media_type, status);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('rog-media', 'rog-media', false, 52428800, array['image/png','image/jpeg','image/webp','video/mp4'])
on conflict (id) do update set public=false, file_size_limit=excluded.file_size_limit, allowed_mime_types=excluded.allowed_mime_types;
