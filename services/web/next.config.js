/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  transpilePackages: ['react-markdown', 'remark-gfm', 'rehype-raw', 'rehype-sanitize'],
}

module.exports = nextConfig
