drop policy if exists "admins_read_family_profiles" on public.rog_user_profiles;
create policy "admins_read_family_profiles"
on public.rog_user_profiles
for select
to authenticated
using (((select auth.jwt()) -> 'app_metadata' ->> 'rog_role') = 'admin');
