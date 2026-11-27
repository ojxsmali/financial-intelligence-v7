-- Financial Intelligence: per-user settings (watchlist, comparison, display preferences).
-- One row per account, readable and writable only by its owner. Guests never touch this table.

create table if not exists public.fi_settings (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint fi_settings_data_is_object check (jsonb_typeof(data) = 'object'),
  constraint fi_settings_data_small check (pg_column_size(data) < 32768)
);

alter table public.fi_settings enable row level security;

drop policy if exists "fi_settings owner select" on public.fi_settings;
drop policy if exists "fi_settings owner insert" on public.fi_settings;
drop policy if exists "fi_settings owner update" on public.fi_settings;
drop policy if exists "fi_settings owner delete" on public.fi_settings;

create policy "fi_settings owner select" on public.fi_settings for select to authenticated using ((select auth.uid()) = user_id);
create policy "fi_settings owner insert" on public.fi_settings for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "fi_settings owner update" on public.fi_settings for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "fi_settings owner delete" on public.fi_settings for delete to authenticated using ((select auth.uid()) = user_id);

revoke all on public.fi_settings from anon;
grant select, insert, update, delete on public.fi_settings to authenticated;
