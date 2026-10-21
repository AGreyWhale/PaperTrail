import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serves a project site under /<repo>/, so the deploy workflow
  // sets BASE_PATH=/PaperTrail/. Unset everywhere else, including dev.
  base: process.env.BASE_PATH ?? '/',
  plugins: [react(), tailwindcss()],
})
