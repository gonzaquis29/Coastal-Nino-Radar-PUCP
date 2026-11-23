/** El logo: dos ondas del mar, la de arriba cálida como el agua de El Niño. Decorativo: el nombre va al lado. */
export function Marca({ tamano = 28 }: { tamano?: number }) {
  return (
    <svg width={tamano} height={tamano} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="26" height="26" rx="7" fill="var(--acento)" />
      <path d="M6 11c2.6-3 5.3-3 8 0s5.4 3 8 0" fill="none" stroke="var(--marca-calida)" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M6 17c2.6-3 5.3-3 8 0s5.4 3 8 0" fill="none" stroke="var(--acento-tinta)" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}
