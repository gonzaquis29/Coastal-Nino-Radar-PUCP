/** El logo: un radar sobre la línea del mar. Decorativo: el nombre va al lado. */
export function Marca({ tamano = 30 }: { tamano?: number }) {
  return (
    <svg width={tamano} height={tamano} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="8" fill="var(--acento)" />
      <circle cx="16" cy="18" r="9" fill="none" stroke="var(--acento-tinta)" strokeWidth="2" opacity=".45" />
      <circle cx="16" cy="18" r="4.5" fill="none" stroke="var(--acento-tinta)" strokeWidth="2" opacity=".8" />
      <path d="M16 18 24 9" stroke="var(--acento-tinta)" strokeWidth="2.4" strokeLinecap="round" />
      <path
        d="M4 25c3-2 5-2 8 0s5 2 8 0 5-2 8 0"
        fill="none"
        stroke="var(--acento-tinta)"
        strokeWidth="2"
        strokeLinecap="round"
        opacity=".7"
      />
    </svg>
  );
}
