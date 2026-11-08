/** @type {import('next').NextConfig} */
// NEXT_DIST_DIR: pasta de build separada, para rodar um segundo servidor local na mesma pasta sem disputar o .next
// (vazio = .next, o padrão; a Vercel não define).
const nextConfig = { reactStrictMode: true, ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}) };
export default nextConfig;
