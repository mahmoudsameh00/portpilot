// Origin → Suez / Cape → destination as one schematic strip (plan §6.0 (7); a real map is F9). The recommended
// lane is solid and blue, the other dashed and grey. No tiles, no third-party request.
import { cn } from "@/lib/utils";

export function RouteStrip({
  origin,
  destination,
  recommended,
  routes,
}: {
  origin: string;
  destination: string;
  recommended: "suez" | "cape" | null;
  routes: string[];
}) {
  const lane = (name: "suez" | "cape") => ({
    stroke: recommended === name ? "var(--primary)" : "var(--chart-2)",
    width: recommended === name ? 3 : 2,
    dash: recommended === name ? undefined : "6 5",
    present: routes.includes(name),
  });
  const suez = lane("suez");
  const cape = lane("cape");
  return (
    <figure className="w-full">
      <svg
        viewBox="0 0 640 150"
        className="h-auto w-full"
        role="img"
        aria-label={`${origin} to ${destination}: via Suez${suez.present ? "" : " (not on this voyage)"}, or via the Cape${
          recommended ? `; recommended via ${recommended === "suez" ? "Suez" : "the Cape"}` : ""
        }`}
      >
        {suez.present ? (
          <path
            d="M70 75 C 170 75, 220 30, 320 30 S 470 75, 570 75"
            fill="none"
            stroke={suez.stroke}
            strokeWidth={suez.width}
            strokeDasharray={suez.dash}
            strokeLinecap="round"
          />
        ) : null}
        {cape.present ? (
          <path
            d="M70 75 C 170 75, 220 125, 320 125 S 470 75, 570 75"
            fill="none"
            stroke={cape.stroke}
            strokeWidth={cape.width}
            strokeDasharray={cape.dash}
            strokeLinecap="round"
          />
        ) : null}
        {routes.includes("direct") ? (
          <line
            x1="70"
            y1="75"
            x2="570"
            y2="75"
            stroke="var(--primary)"
            strokeWidth="3"
            strokeLinecap="round"
          />
        ) : null}
        {(
          [
            ["Suez Canal", 30, suez],
            ["Cape of Good Hope", 125, cape],
          ] as const
        ).map(([label, y, l]) =>
          l.present ? (
            <g key={label}>
              <circle cx="320" cy={y} r="6" fill="var(--card)" stroke={l.stroke} strokeWidth="2.5" />
              <text
                x="320"
                y={y === 30 ? 16 : 145}
                textAnchor="middle"
                className={cn(
                  "text-[11px]",
                  recommended && l.stroke === "var(--primary)" ? "font-semibold" : "",
                )}
                fill="var(--foreground)"
              >
                {label}
              </text>
            </g>
          ) : null,
        )}
        {(
          [
            [origin, 70],
            [destination, 570],
          ] as const
        ).map(([code, x]) => (
          <g key={`${code}-${x}`}>
            <circle cx={x} cy="75" r="8" fill="var(--navy)" />
            <circle cx={x} cy="75" r="3" fill="var(--lane)" />
            <text
              x={x}
              y="102"
              textAnchor="middle"
              className="font-mono text-[12px] font-semibold"
              fill="var(--foreground)"
            >
              {code}
            </text>
          </g>
        ))}
      </svg>
    </figure>
  );
}
