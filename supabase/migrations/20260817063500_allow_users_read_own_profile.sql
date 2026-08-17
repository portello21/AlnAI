grant select on table public.rog_user_profiles to authenticated;

drop policy if exists "users_read_own_profile" on public.rog_user_profiles;

create policy "users_read_own_profile"
on public.rog_user_profiles
for select
to authenticated
using ((select auth.uid()) = user_id);
