import type { Metadata, Viewport } from "next";
import { Archivo, Inter } from "next/font/google";
import "./globals.css";
import "../styles/shell.css";
// Tema OrçaAI (protótipo, referência Mercury): carregado por último, sobrescreve tokens e formas.
import "../styles/tema-orcaai.css";
import { Shell } from "@/components/shell/Shell";

const inter = Inter({ subsets: ["latin"], variable: "--fonte-texto", display: "swap" });
const archivo = Archivo({ subsets: ["latin"], axes: ["wdth"], variable: "--fonte-titulo", display: "swap" });

export const metadata: Metadata = {
  title: "OrçaAI — do projeto ao orçamento",
  description:
    "A OrçaAI lê a lista de materiais do projeto, aponta o que ficou faltando, pesquisa preços com fonte e diz se cabe no orçamento do cliente.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#171721" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${archivo.variable}`}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
