alter table public.rog_user_profiles
  add column if not exists password_change_required boolean not null default false,
  add column if not exists password_change_issued_at timestamptz;

drop policy if exists "deny_client_update" on public.rog_user_profiles;

drop policy if exists "users_clear_own_password_requirement" on public.rog_user_profiles;
create policy "users_clear_own_password_requirement"
on public.rog_user_profiles
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "admins_read_family_profiles" on public.rog_user_profiles;
create policy "admins_read_family_profiles"
on public.rog_user_profiles
for select
to authenticated
using ((select auth.jwt() -> 'app_metadata' ->> 'rog_role') = 'admin');

drop policy if exists "admins_manage_family_profiles" on public.rog_user_profiles;
create policy "admins_manage_family_profiles"
on public.rog_user_profiles
for update
to authenticated
using ((select auth.jwt() -> 'app_metadata' ->> 'rog_role') = 'admin')
with check ((select auth.jwt() -> 'app_metadata' ->> 'rog_role') = 'admin');

revoke update on public.rog_user_profiles from authenticated;
grant update (active, password_change_required, password_change_issued_at, updated_at)
on public.rog_user_profiles to authenticated;

update public.rog_user_profiles
set password_change_required = true,
    password_change_issued_at = now()
where profile = 'allan';
