import { Caderno } from "@/components/Caderno";

// Página da demonstração (botão "Visualizar Demo" da landing): o mesmo caderno da /nova, com passos numerados,
// exemplos para baixar (2 por formato) e a área de arrastar e soltar. O envio é o real: pesquisa ao vivo em /obra/[id].
export default function Demo() {
  return <Caderno demo />;
}
