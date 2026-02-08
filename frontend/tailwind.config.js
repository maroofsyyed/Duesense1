/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#09090b',
        surface: '#18181b',
        'surface-hl': '#27272a',
        border: '#27272a',
        primary: '#6366f1',
        'primary-hover': '#4f46e5',
        secondary: '#3b82f6',
        accent: '#8b5cf6',
        success: '#10b981',
        warning: '#f59e0b',
        destructive: '#ef4444',
        'text-primary': '#fafafa',
        'text-secondary': '#a1a1aa',
        'text-muted': '#71717a',
      },
      fontFamily: {
        heading: ['Chivo', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
