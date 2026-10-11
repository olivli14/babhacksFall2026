-- AI-generated with Claude (Anthropic).
-- Paste into Supabase: SQL Editor -> New query -> Run.
-- RLS is on with no policies: only the backend's secret key can read or write.

-- Raw onboarding form submissions, exactly as entered.
create table if not exists business_inputs (
  id bigint generated always as identity primary key,
  url text not null,
  city text,
  annual_revenue double precision,
  domain text,                           -- filled in after onboarding
  status text not null default 'pending' check (status in ('pending', 'ok', 'error')),
  error text,
  submitted_at timestamptz default now()
);

-- One row per onboarded business location (the classified profile).
create table if not exists businesses (
  id bigint generated always as identity primary key,
  domain text not null,
  location_key text not null,            -- lowercased address, so chain branches don't collide
  name text,
  logo_url text,
  address text,
  lat double precision,
  lon double precision,
  side text check (side in ('heat_hurt', 'cold_hurt', 'needs_review')),
  confidence double precision,
  reason_codes jsonb,
  business_type text,
  baseline_temp_f double precision,
  annual_revenue double precision,
  dollars_per_degree double precision,
  dollars_per_degree_source text,
  gemini_city text,
  distance_miles double precision,
  location_source text,
  menu_url text,
  onboarded_at timestamptz default now(),
  unique (domain, location_key)
);

create table if not exists hedge_plans (
  id bigint generated always as identity primary key,
  city text not null,
  date date not null,
  plan jsonb not null,
  generated_at timestamptz default now(),
  unique (city, date)
);

-- Every daily high we pull, per Gemini city.
-- source 'archive': observed (Open-Meteo archive); 'forecast': ensemble mean, members in members.
create table if not exists weather_daily (
  city text not null,
  date date not null,
  source text not null check (source in ('archive', 'forecast')),
  high_f double precision not null,
  members jsonb,
  lat double precision,
  lon double precision,
  fetched_at timestamptz default now(),
  primary key (city, date, source)
);

alter table business_inputs enable row level security;
alter table businesses enable row level security;
alter table hedge_plans enable row level security;
alter table weather_daily enable row level security;
