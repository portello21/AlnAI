-- Make the server-only contract explicit. The service role has BYPASSRLS;
-- anon/authenticated clients receive no rows even if legacy grants exist.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'conversation_archives',
    'document_chunks',
    'long_term_memory',
    'memories_v2',
    'response_feedback',
    'rog_api_usage',
    'rog_audit_events',
    'rog_user_profiles'
  ]
  loop
    if to_regclass('public.' || table_name) is not null then
      execute format('alter table public.%I enable row level security', table_name);
      execute format('drop policy if exists server_only_deny_clients on public.%I', table_name);
      execute format(
        'create policy server_only_deny_clients on public.%I as restrictive for all to anon, authenticated using (false) with check (false)',
        table_name
      );
    end if;
  end loop;
end
$$;
