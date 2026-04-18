-- Fridge Observer — Initial Schema Migration
-- Migrating from SQLite to Supabase Postgres

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ── Users ─────────────────────────────────────────────────────
-- Note: Supabase Auth handles authentication.
-- This table stores additional profile data linked to auth.users
create table if not exists public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    display_name text not null,
    created_at  timestamptz not null default now(),
    last_login  timestamptz
);

-- ── Food items ────────────────────────────────────────────────
create table if not exists public.food_items (
    id           bigserial primary key,
    user_id      uuid not null references auth.users(id) on delete cascade,
    name         text not null,
    category     text not null check (category in ('fruits','vegetables','dairy','beverages','meat','packaged_goods')),
    quantity     integer not null default 1,
    expiry_date  date,
    expiry_source text not null default 'estimated' check (expiry_source in ('estimated','manual')),
    added_at     timestamptz not null default now(),
    thumbnail    text,
    notes        text
);

-- ── Activity log ──────────────────────────────────────────────
create table if not exists public.activity_log (
    id          bigserial primary key,
    user_id     uuid not null references auth.users(id) on delete cascade,
    item_id     bigint,
    item_name   text not null,
    action      text not null check (action in ('added','removed','updated','expired')),
    source      text not null check (source in ('automatic','manual')),
    occurred_at timestamptz not null default now()
);

-- ── Temperature readings ──────────────────────────────────────
create table if not exists public.temperature_readings (
    id            bigserial primary key,
    user_id       uuid not null references auth.users(id) on delete cascade,
    compartment   text not null check (compartment in ('fridge','freezer')),
    value_celsius real not null,
    recorded_at   timestamptz not null default now()
);

-- ── Recipes ───────────────────────────────────────────────────
create table if not exists public.recipes (
    id           bigserial primary key,
    name         text not null,
    description  text,
    cuisine      text,
    dietary_tags jsonb default '[]'::jsonb,
    prep_minutes integer,
    instructions text not null,
    image_url    text
);

-- ── Recipe ingredients ────────────────────────────────────────
create table if not exists public.recipe_ingredients (
    id               bigserial primary key,
    recipe_id        bigint not null references public.recipes(id) on delete cascade,
    name             text not null,
    category         text,
    is_pantry_staple boolean not null default false
);

-- ── Recipe favorites (per user) ───────────────────────────────
create table if not exists public.recipe_favorites (
    user_id   uuid not null references auth.users(id) on delete cascade,
    recipe_id bigint not null references public.recipes(id) on delete cascade,
    saved_at  timestamptz not null default now(),
    primary key (user_id, recipe_id)
);

-- ── Shopping queue ────────────────────────────────────────────
create table if not exists public.shopping_queue (
    id         bigserial primary key,
    user_id    uuid not null references auth.users(id) on delete cascade,
    item_name  text not null,
    queued_at  timestamptz not null default now(),
    attempts   integer not null default 0
);

-- ── Settings (per user) ───────────────────────────────────────
create table if not exists public.settings (
    user_id uuid not null references auth.users(id) on delete cascade,
    key     text not null,
    value   text not null,
    primary key (user_id, key)
);

-- ── Indexes ───────────────────────────────────────────────────
create index if not exists food_items_user_id_idx on public.food_items(user_id);
create index if not exists food_items_expiry_idx on public.food_items(expiry_date);
create index if not exists activity_log_user_id_idx on public.activity_log(user_id);
create index if not exists activity_log_occurred_at_idx on public.activity_log(occurred_at desc);
create index if not exists temperature_readings_user_id_idx on public.temperature_readings(user_id);
create index if not exists settings_user_id_idx on public.settings(user_id);

-- ── Row Level Security ────────────────────────────────────────
alter table public.profiles enable row level security;
alter table public.food_items enable row level security;
alter table public.activity_log enable row level security;
alter table public.temperature_readings enable row level security;
alter table public.recipe_favorites enable row level security;
alter table public.shopping_queue enable row level security;
alter table public.settings enable row level security;
-- Recipes are shared (no RLS needed — all users see all recipes)

-- Profiles: users can only read/update their own profile
create policy "Users can view own profile"
    on public.profiles for select
    using (auth.uid() = id);

create policy "Users can update own profile"
    on public.profiles for update
    using (auth.uid() = id);

create policy "Users can insert own profile"
    on public.profiles for insert
    with check (auth.uid() = id);

-- Food items: users can only CRUD their own items
create policy "Users can manage own food items"
    on public.food_items for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Activity log: users can only read/insert their own logs
create policy "Users can manage own activity log"
    on public.activity_log for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Temperature readings: users can only manage their own
create policy "Users can manage own temperature readings"
    on public.temperature_readings for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Recipe favorites: per user
create policy "Users can manage own favorites"
    on public.recipe_favorites for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Shopping queue: per user
create policy "Users can manage own shopping queue"
    on public.shopping_queue for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Settings: per user
create policy "Users can manage own settings"
    on public.settings for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── Realtime ──────────────────────────────────────────────────
-- Enable realtime for tables that need live updates
alter publication supabase_realtime add table public.food_items;
alter publication supabase_realtime add table public.activity_log;
alter publication supabase_realtime add table public.temperature_readings;

-- ── Profile auto-creation trigger ────────────────────────────
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, display_name)
    values (
        new.id,
        coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1))
    );
    return new;
end;
$$;

create or replace trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();
