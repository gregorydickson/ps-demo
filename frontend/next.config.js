/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',  // Required for Docker deployment

  // Environment variables available at runtime
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
}

module.exports = nextConfig
