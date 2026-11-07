-- ############################################################################################
-- # NÃO RODAR: frete em PAUSA (decisão 07/11) e este seed é INCOMPATÍVEL com o SQL real
-- # (sql/002_orcamentos.sql): lá `id` é uuid, `cep` é NOT NULL, `lat/lon` são numeric(9,6)
-- # e há a coluna `ativo`. Antes de reativar o frete, reescreva o seed para esse schema
-- # (insert sem id, com cep de cada loja) e ligue FRETE_ATIVO=true.
-- ############################################################################################

-- Fatia C: lojas para o frete (E7). Gerado a partir de src/busca.py (LOJAS): `dominio` precisa ser IDÊNTICO
-- ao domínio que a busca da Fatia B grava em orcamento_itens.fontes[].dominio.
--
-- ATENÇÃO — valores ESTIMADOS: quase todas são e-commerce, então não há CEP/coordenadas e o frete é um valor
-- fixo por loja (frete_base = R$ 35.00, rs_por_km = 0, pedido_minimo = 0). Não é tabela oficial das lojas:
-- na demo, diga "frete estimado". Para uma loja física de Recife, preencha cep/lat/lon/rs_por_km/pedido_minimo.
--
-- Pode rodar de novo sem duplicar (on conflict). Se o Samuel já criou `fornecedores` com outras colunas,
-- confira antes: o código lê id, nome, dominio, cep, frete_base, rs_por_km, pedido_minimo, lat, lon.

create table if not exists fornecedores (
    id            text primary key,
    nome          text not null,
    dominio       text not null,
    cep           text,                           -- null em e-commerce
    frete_base    numeric not null default 0,
    rs_por_km     numeric not null default 0,
    pedido_minimo numeric not null default 0,
    lat           double precision,
    lon           double precision
);

insert into fornecedores (id, nome, dominio, frete_base, rs_por_km, pedido_minimo) values
  ('leroymerlin.com.br', 'Leroy Merlin', 'leroymerlin.com.br', 35.00, 0, 0),
  ('cec.com.br', 'C&C', 'cec.com.br', 35.00, 0, 0),
  ('telhanorte.com.br', 'Telhanorte', 'telhanorte.com.br', 35.00, 0, 0),
  ('obramax.com.br', 'Obramax', 'obramax.com.br', 35.00, 0, 0),
  ('ferreiracosta.com', 'Ferreira Costa', 'ferreiracosta.com', 35.00, 0, 0),
  ('madeiramadeira.com.br', 'MadeiraMadeira', 'madeiramadeira.com.br', 35.00, 0, 0),
  ('amazon.com.br', 'Amazon', 'amazon.com.br', 35.00, 0, 0),
  ('mercadolivre.com.br', 'Mercado Livre', 'mercadolivre.com.br', 35.00, 0, 0),
  ('magazineluiza.com.br', 'Magazine Luiza', 'magazineluiza.com.br', 35.00, 0, 0),
  ('casasbahia.com.br', 'Casas Bahia', 'casasbahia.com.br', 35.00, 0, 0),
  ('americanas.com.br', 'Americanas', 'americanas.com.br', 35.00, 0, 0),
  ('dicico.com.br', 'Dicico', 'dicico.com.br', 35.00, 0, 0),
  ('loja.suvinil.com.br', 'Loja Suvinil', 'loja.suvinil.com.br', 35.00, 0, 0),
  ('lojadexco.com.br', 'Loja Dexco (Deca)', 'lojadexco.com.br', 35.00, 0, 0),
  ('tramontina.com.br', 'Loja Tramontina', 'tramontina.com.br', 35.00, 0, 0),
  ('sertao.com.br', 'Sertão', 'sertao.com.br', 35.00, 0, 0),
  ('padovani.com.br', 'Padovani', 'padovani.com.br', 35.00, 0, 0),
  ('tumelero.com.br', 'Tumelero', 'tumelero.com.br', 35.00, 0, 0)
on conflict (id) do update set nome = excluded.nome, dominio = excluded.dominio;   -- não sobrescreve frete já ajustado
