-- Trilha de auditoria das execuções do agente.
-- Rode no SQL Editor do Supabase (ou é aplicado automaticamente no Postgres local).

create table if not exists agent_runs (
    id            uuid primary key default gen_random_uuid(),
    created_at    timestamptz not null default now(),
    task          text not null,
    status        text not null,          -- completed | max_steps_reached | error
    output        text,
    steps         jsonb not null default '[]'::jsonb,
    model         text,
    prompt_tokens integer default 0,
    completion_tokens integer default 0,
    latency_ms    integer,
    trace_id      text                    -- link para o trace no Langfuse
);

create index if not exists agent_runs_created_at_idx on agent_runs (created_at desc);
