-- Cache da pesquisa de preço (fatia B). Bloco para o arquivo SQL único da fatia A;
-- até ele existir, pode ser rodado sozinho no SQL Editor do Supabase.
--
-- Guarda o que NÃO depende da quantidade do orçamento: as ofertas conferidas e a imagem escolhida.
-- A conta (mediana, confiança, nº de embalagens) é refeita a cada uso por src/calculo.py.
-- Válido por 7 dias (PESQUISA_CACHE_DIAS); vencido ainda serve de reserva ("preço de dd/mm").

create table if not exists cache_precos (
    chave          text primary key,          -- descrição normalizada (src/cache.py: chave_cache)
    descricao      text not null,             -- descrição original, para leitura humana
    ofertas        jsonb not null default '[]'::jsonb,   -- [{loja, dominio, url, titulo, preco, embalagem, mesmo_produto}]
    imagem_url     text,                      -- a imagem escolhida: o mesmo produto mostra sempre a mesma foto
    modelo         text,                      -- modelo que extraiu os preços
    provedor       text,                      -- tavily | duckduckgo
    atualizado_em  timestamptz not null default now()
);

create index if not exists cache_precos_atualizado_idx on cache_precos (atualizado_em desc);

-- Só o backend (chave secreta, que ignora RLS) lê e grava. O site não precisa desta tabela.
alter table cache_precos enable row level security;
