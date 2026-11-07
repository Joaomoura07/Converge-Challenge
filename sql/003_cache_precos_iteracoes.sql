-- Fatia B: o cache passa a guardar quantas vezes o agente refez a busca do produto.
-- Sem isso, item que vem do cache aparece na tela sem o selo "A IA refez a busca N vezes".
-- Opcional: enquanto esta coluna não existir, src/cache.py grava sem ela (e lê 0).
-- Rodar no SQL Editor do Supabase.

alter table cache_precos add column if not exists iteracoes int not null default 0;
