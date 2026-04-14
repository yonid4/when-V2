-- Fix notifications RLS SELECT policy
-- The "anon can select notifications" policy was created without TO anon,
-- which grants all roles (including authenticated) access to all rows,
-- overriding the user-scoped select policy.

alter table notifications enable row level security;

drop policy if exists "notifications_select_own" on notifications;
create policy "notifications_select_own"
  on notifications for select
  using (auth.uid() = user_id);

drop policy if exists "anon can select notifications" on public.notifications;
create policy "anon can select notifications"
  on public.notifications for select to anon
  using (true);
