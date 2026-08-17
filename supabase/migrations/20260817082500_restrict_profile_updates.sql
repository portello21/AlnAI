drop policy if exists "admins_manage_family_profiles" on public.rog_user_profiles;

revoke update on public.rog_user_profiles from authenticated;
grant update (password_change_required, password_change_issued_at)
on public.rog_user_profiles to authenticated;
