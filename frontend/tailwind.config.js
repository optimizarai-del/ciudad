/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#0A0A0A',
          50:  '#F5F5F5',
          100: '#E8E8E8',
          200: '#D4D4D4',
          300: '#B0B0B0',
          400: '#888888',
          500: '#0A0A0A',
          600: '#000000',
          700: '#000000',
          800: '#000000',
          900: '#000000',
        },
        accent: {
          DEFAULT: '#555555',
          50:  '#F7F7F7',
          100: '#EFEFEF',
          200: '#E0E0E0',
          300: '#C8C8C8',
          400: '#9A9A9A',
          500: '#555555',
          600: '#404040',
          700: '#2E2E2E',
          800: '#1A1A1A',
          900: '#0A0A0A',
        },
        warn:    '#B45309',
        neutral: {
          DEFAULT: '#F7F7F7',
          50:  '#FFFFFF',
          100: '#FAFAFA',
          200: '#F5F5F5',
          300: '#EBEBEB',
          400: '#E0E0E0',
        },
        bg:       '#F7F7F7',
        surface:  '#FFFFFF',
        surface2: '#FAFAFA',
        border:   '#E5E5E5',
        text:     '#0A0A0A',
        muted:    '#737373',
        success:  '#16A34A',
        danger:   '#DC2626',
      },
      fontFamily: {
        display: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Helvetica Neue', 'sans-serif'],
        sans:    ['Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'sans-serif'],
      },
      letterSpacing: {
        tightest: '-0.04em',
        tighter:  '-0.025em',
      },
      boxShadow: {
        'soft': '0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04)',
        'card': '0 1px 3px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.06)',
        'lift': '0 4px 8px rgba(0,0,0,0.08), 0 16px 40px rgba(0,0,0,0.08)',
      },
      animation: {
        'fade-in':  'fadeIn  0.5s ease-out',
        'slide-up': 'slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scaleIn 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        fadeIn:  { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: {
          '0%':   { transform: 'translateY(24px)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
        scaleIn: {
          '0%':   { transform: 'scale(0.96)', opacity: '0' },
          '100%': { transform: 'scale(1)',    opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
