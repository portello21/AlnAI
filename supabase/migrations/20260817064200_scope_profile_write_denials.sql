drop policy if exists "server_only_deny_clients" on public.rog_user_profiles;

drop policy if exists "deny_client_insert" on public.rog_user_profiles;
create policy "deny_client_insert"
on public.rog_user_profiles
as restrictive
for insert
to anon, authenticated
with check (false);

drop policy if exists "deny_client_update" on public.rog_user_profiles;
create policy "deny_client_update"
on public.rog_user_profiles
as restrictive
for update
to anon, authenticated
using (false)
with check (false);

drop policy if exists "deny_client_delete" on public.rog_user_profiles;
create policy "deny_client_delete"
on public.rog_user_profiles
as restrictive
for delete
to anon, authenticated
using (false);
