// PortPilot: a P-shaped port with an outbound navigation arrow. Decorative beside the written name.
export function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden="true" focusable="false">
      <path
        d="M6 27V5h10a7 7 0 0 1 0 14h-5"
        fill="none"
        stroke={dark ? "var(--on-navy)" : "var(--navy)"}
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="m16 27 10-10m-7 0h7v7"
        fill="none"
        stroke={dark ? "var(--lane)" : "var(--primary)"}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
