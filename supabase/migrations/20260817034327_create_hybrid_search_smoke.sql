create or replace function public.rog_healthcheck()
returns boolean
language sql
stable
security invoker
set search_path = ''
as 'select true';

revoke all on function public.rog_healthcheck() from public, anon, authenticated;
grant execute on function public.rog_healthcheck() to service_role;
