// Cliente do Supabase NO NAVEGADOR: só a chave pública (anon). A chave de serviço fica no backend.
// A leitura anon de orcamentos e orcamento_itens é a política da demo sintética (sql/002_orcamentos.sql).

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let cliente: SupabaseClient | null | undefined;

export function supabaseConfigurado(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}

/** null quando as variáveis NEXT_PUBLIC_SUPABASE_* não existem (a tela mostra o aviso de configuração). */
export function obterSupabase(): SupabaseClient | null {
  if (cliente !== undefined) return cliente;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const chave = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  cliente = url && chave ? createClient(url, chave, { auth: { persistSession: false, autoRefreshToken: false } }) : null;
  return cliente;
}
