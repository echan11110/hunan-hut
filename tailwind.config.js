/** Tailwind config for the static build.
 * Rebuild CSS after editing HTML classes:
 *   npx tailwindcss@3.4.17 -c tailwind.config.js -i src/tailwind.css -o assets/tailwind.css --minify
 */
module.exports = {
  content: ['./index.html', './menu/index.html'],
  theme: {
    extend: {
      colors: {
        brand: {
          red:      '#DC2626',
          redLight: '#F87171',
          gold:     '#CA8A04',
          goldLight:'#FCD34D',
          dark:     '#2E1B14',
          darker:   '#1A100C',
          cream:    '#FEF2F2',
          muted:    '#7F1D1D',
        },
      },
      fontFamily: {
        display: ['"Playfair Display SC"', 'Georgia', 'serif'],
        body:    ['Karla', 'system-ui', 'sans-serif'],
      },
    },
  },
};
