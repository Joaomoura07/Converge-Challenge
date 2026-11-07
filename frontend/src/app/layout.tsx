import type { Metadata, Viewport } from "next";
import "./globals.css";
import "../styles/shell.css";
import { Shell } from "@/components/shell/Shell";

export const metadata: Metadata = {
  title: "Orça — Nova obra",
  description: "Caderno de materiais digital: monte a lista da obra e envie para a IA pesquisar os preços.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
