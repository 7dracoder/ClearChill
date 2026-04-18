-- Email OTP table for custom verification flow
-- Uses email instead of user_id since user may not be confirmed yet

create table if not exists public.email_otps (
    id         bigserial primary key,
    email      text not null,
    code       text not null,
    expires_at timestamptz not null,
    used       boolean not null default false,
    created_at timestamptz not null default now()
);

create index if not exists email_otps_email_idx on public.email_otps(email);
create index if not exists email_otps_expires_idx on public.email_otps(expires_at);

-- No RLS needed — only accessed via service role key from backend
