-- ============================================================================
-- VOICE INTEGRATION MIGRATION
-- Adds support for Google Home voice interaction with pending items
-- ============================================================================

-- ── Pending Items Table ──────────────────────────────────────────────────

-- Items detected by camera that are waiting for user voice input
create table if not exists public.pending_items (
    id               bigserial primary key,
    user_id          uuid not null references auth.users(id) on delete cascade,
    session_id       text not null,
    item_name        text not null,
    category         text not null check (category in ('fruits','vegetables','dairy','beverages','meat','packaged_goods')),
    confidence       real not null check (confidence >= 0 and confidence <= 1),
    is_packaged      boolean not null default false,
    estimated_expiry_days integer,
    needs_quantity   boolean not null default true,
    needs_expiry_date boolean not null default false,
    thumbnail        text,
    created_at       timestamptz not null default now(),
    expires_at       timestamptz not null default (now() + interval '24 hours')
);

-- ── Capture Sessions Table ───────────────────────────────────────────────

-- Track each door open/close session for analytics
create table if not exists public.capture_sessions (
    id               bigserial primary key,
    user_id          uuid not null references auth.users(id) on delete cascade,
    session_id       text not null unique,
    started_at       timestamptz not null,
    ended_at         timestamptz,
    duration_seconds integer,
    frames_captured  integer not null default 0,
    items_detected   integer not null default 0,
    items_added      integer not null default 0,
    items_removed    integer not null default 0,
    status           text not null default 'processing' check (status in ('processing','completed','failed')),
    created_at       timestamptz not null default now()
);

-- ── Voice Interactions Table ─────────────────────────────────────────────

-- Log all voice interactions for debugging and analytics
create table if not exists public.voice_interactions (
    id               bigserial primary key,
    user_id          uuid not null references auth.users(id) on delete cascade,
    session_id       text,
    intent           text not null,
    query            text,
    response         text,
    success          boolean not null default true,
    error_message    text,
    created_at       timestamptz not null default now()
);

-- ── Indexes ──────────────────────────────────────────────────────────────

create index if not exists pending_items_user_id_idx on public.pending_items(user_id);
create index if not exists pending_items_session_id_idx on public.pending_items(session_id);
create index if not exists pending_items_created_at_idx on public.pending_items(created_at desc);
create index if not exists pending_items_expires_at_idx on public.pending_items(expires_at);

create index if not exists capture_sessions_user_id_idx on public.capture_sessions(user_id);
create index if not exists capture_sessions_session_id_idx on public.capture_sessions(session_id);
create index if not exists capture_sessions_created_at_idx on public.capture_sessions(created_at desc);

create index if not exists voice_interactions_user_id_idx on public.voice_interactions(user_id);
create index if not exists voice_interactions_created_at_idx on public.voice_interactions(created_at desc);

-- ── Row Level Security ───────────────────────────────────────────────────

alter table public.pending_items enable row level security;
alter table public.capture_sessions enable row level security;
alter table public.voice_interactions enable row level security;

-- Pending items policies
drop policy if exists "Users can manage own pending items" on public.pending_items;
create policy "Users can manage own pending items"
    on public.pending_items for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Capture sessions policies
drop policy if exists "Users can view own capture sessions" on public.capture_sessions;
create policy "Users can view own capture sessions"
    on public.capture_sessions for select
    using (auth.uid() = user_id);

drop policy if exists "Users can insert own capture sessions" on public.capture_sessions;
create policy "Users can insert own capture sessions"
    on public.capture_sessions for insert
    with check (auth.uid() = user_id);

drop policy if exists "Users can update own capture sessions" on public.capture_sessions;
create policy "Users can update own capture sessions"
    on public.capture_sessions for update
    using (auth.uid() = user_id);

-- Voice interactions policies
drop policy if exists "Users can manage own voice interactions" on public.voice_interactions;
create policy "Users can manage own voice interactions"
    on public.voice_interactions for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── Realtime ─────────────────────────────────────────────────────────────

-- Enable realtime for pending items (so web app updates instantly)
do $$
begin
    alter publication supabase_realtime add table public.pending_items;
exception when duplicate_object then
    null;
end $$;

do $$
begin
    alter publication supabase_realtime add table public.capture_sessions;
exception when duplicate_object then
    null;
end $$;

-- ── Functions ────────────────────────────────────────────────────────────

-- Auto-delete expired pending items (cleanup job)
create or replace function public.cleanup_expired_pending_items()
returns void
language plpgsql
security definer
as $$
begin
    delete from public.pending_items
    where expires_at < now();
end;
$$;

-- Function to get pending items count for a user
create or replace function public.get_pending_items_count(p_user_id uuid)
returns integer
language plpgsql
security definer
as $$
declare
    item_count integer;
begin
    select count(*) into item_count
    from public.pending_items
    where user_id = p_user_id
    and expires_at > now();
    
    return item_count;
end;
$$;

-- Function to move pending item to inventory
create or replace function public.confirm_pending_item(
    p_pending_item_id bigint,
    p_quantity integer,
    p_expiry_date date default null
)
returns bigint
language plpgsql
security definer
as $$
declare
    v_user_id uuid;
    v_item_name text;
    v_category text;
    v_new_item_id bigint;
begin
    -- Get pending item details
    select user_id, item_name, category
    into v_user_id, v_item_name, v_category
    from public.pending_items
    where id = p_pending_item_id
    and user_id = auth.uid();
    
    if not found then
        raise exception 'Pending item not found or access denied';
    end if;
    
    -- Insert into food_items
    insert into public.food_items (
        user_id,
        name,
        category,
        quantity,
        expiry_date,
        added_via
    ) values (
        v_user_id,
        v_item_name,
        v_category,
        p_quantity,
        p_expiry_date,
        'voice'
    )
    returning id into v_new_item_id;
    
    -- Log activity
    insert into public.activity_log (
        user_id,
        item_id,
        item_name,
        action,
        source
    ) values (
        v_user_id,
        v_new_item_id,
        v_item_name,
        'added',
        'automatic'
    );
    
    -- Delete pending item
    delete from public.pending_items
    where id = p_pending_item_id;
    
    return v_new_item_id;
end;
$$;

-- ── Scheduled Jobs (Optional - requires pg_cron extension) ───────────────

-- Clean up expired pending items every hour
-- Uncomment if you have pg_cron enabled:
-- select cron.schedule(
--     'cleanup-expired-pending-items',
--     '0 * * * *',  -- Every hour
--     $$select public.cleanup_expired_pending_items()$$
-- );

-- ── Sample Data (for testing) ────────────────────────────────────────────

-- Uncomment to insert test data:
-- insert into public.pending_items (user_id, session_id, item_name, category, confidence, is_packaged, needs_expiry_date)
-- values 
--     (auth.uid(), 'test_session_001', 'Milk', 'dairy', 0.92, true, true),
--     (auth.uid(), 'test_session_001', 'Eggs', 'dairy', 0.88, true, true),
--     (auth.uid(), 'test_session_001', 'Chicken Breast', 'meat', 0.85, false, false);

-- ============================================================================
-- MIGRATION COMPLETE!
-- ============================================================================
-- New tables created:
--   • pending_items - Items waiting for voice confirmation
--   • capture_sessions - Door open/close session tracking
--   • voice_interactions - Voice command logging
--
-- New functions created:
--   • cleanup_expired_pending_items() - Auto-cleanup
--   • get_pending_items_count() - Count pending items
--   • confirm_pending_item() - Move pending → inventory
-- ============================================================================
