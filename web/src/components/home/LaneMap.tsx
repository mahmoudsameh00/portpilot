// The night-ops map: a dot-matrix of the land between the North Sea and the China Sea, PortPilot's two trade
// lanes (via Suez, via the Cape) and vessels moving along them. Pure SVG drawn on the server; no map tiles, no
// third-party request (plan F9 keeps maps out; this is a schematic, not a chart of real positions).
import { MotionGuard } from "./MotionGuard";

const W = 1000;
const LON0 = -25;
const LON1 = 130;
const LAT0 = -42;
const LAT1 = 62;
const H = Math.round((W * (LAT1 - LAT0)) / (LON1 - LON0));
const px = (lon: number) => ((lon - LON0) / (LON1 - LON0)) * W;
const py = (lat: number) => ((LAT1 - lat) / (LAT1 - LAT0)) * H;

type LL = readonly [number, number];

// Coarse land outlines (lon, lat) — enough for a dot texture, not for navigation.
const LAND: LL[][] = [
  // Africa
  [
    [-17, 21],
    [-17, 14],
    [-12, 7],
    [-8, 4],
    [5, 4],
    [9, 4],
    [10, -1],
    [13, -6],
    [12, -17],
    [15, -27],
    [18, -34],
    [20, -35],
    [26, -34],
    [32, -29],
    [35, -24],
    [40, -15],
    [40, -10],
    [39, -5],
    [42, 0],
    [48, 5],
    [51, 12],
    [43, 12],
    [39, 16],
    [37, 21],
    [35, 24],
    [33, 28],
    [32, 31],
    [25, 32],
    [20, 31],
    [11, 33],
    [10, 37],
    [-1, 36],
    [-6, 36],
    [-10, 30],
    [-13, 27],
  ],
  // Madagascar
  [
    [44, -25],
    [47, -25],
    [50, -15],
    [49, -12],
    [44, -17],
  ],
  // Arabia
  [
    [35, 30],
    [39, 22],
    [43, 13],
    [45, 13],
    [52, 16],
    [59, 22],
    [56, 26],
    [51, 25],
    [48, 29],
    [44, 30],
    [39, 32],
    [35, 32],
  ],
  // Europe + Anatolia
  [
    [-9, 37],
    [-9, 43],
    [-2, 44],
    [-5, 48],
    [2, 51],
    [5, 53],
    [8, 55],
    [10, 57],
    [11, 59],
    [5, 59],
    [5, 62],
    [30, 62],
    [40, 62],
    [40, 42],
    [36, 41],
    [28, 41],
    [26, 38],
    [23, 36],
    [21, 39],
    [19, 42],
    [13, 45],
    [16, 41],
    [18, 40],
    [15, 38],
    [12, 38],
    [10, 44],
    [3, 43],
    [-2, 37],
  ],
  // Great Britain + Ireland
  [
    [-5, 50],
    [1, 51],
    [2, 53],
    [-2, 56],
    [-5, 58],
    [-6, 56],
    [-3, 54],
    [-5, 52],
  ],
  [
    [-10, 52],
    [-6, 52],
    [-6, 55],
    [-10, 54],
  ],
  // Asia mainland
  [
    [40, 42],
    [50, 45],
    [60, 45],
    [66, 25],
    [68, 24],
    [73, 20],
    [77, 8],
    [80, 15],
    [88, 22],
    [92, 20],
    [98, 16],
    [100, 8],
    [104, 1.5],
    [104, 10],
    [108, 12],
    [109, 20],
    [117, 23],
    [122, 30],
    [121, 38],
    [126, 40],
    [130, 42],
    [130, 62],
    [40, 62],
  ],
  // Sri Lanka, Sumatra, Borneo, Japan (south), Taiwan
  [
    [80, 6],
    [82, 7],
    [81, 9],
    [80, 8],
  ],
  [
    [95, 5],
    [98, 4],
    [106, -6],
    [102, -4],
  ],
  [
    [109, 1],
    [117, 7],
    [119, 1],
    [116, -4],
    [110, -3],
  ],
  [
    [129, 31],
    [130, 34],
    [127, 34],
  ],
  [
    [120, 22],
    [122, 25],
    [121, 23],
  ],
];

function inside(lon: number, lat: number, poly: LL[]): boolean {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]!;
    const [xj, yj] = poly[j]!;
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

const STEP = 2;
const DOTS: string = (() => {
  const parts: string[] = [];
  for (let lat = LAT1 - 1; lat > LAT0; lat -= STEP) {
    for (let lon = LON0 + 1; lon < LON1; lon += STEP) {
      if (LAND.some((p) => inside(lon, lat, p))) parts.push(`M${px(lon).toFixed(1)} ${py(lat).toFixed(1)}h0`);
    }
  }
  return parts.join("");
})();

// A smooth path through waypoints (Catmull-Rom → cubic Bézier).
function smooth(points: LL[]): string {
  const p = points.map(([lon, lat]) => [px(lon), py(lat)] as const);
  let d = `M${p[0]![0].toFixed(1)} ${p[0]![1].toFixed(1)}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] ?? p[i]!;
    const p1 = p[i]!;
    const p2 = p[i + 1]!;
    const p3 = p[i + 2] ?? p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${c1[0]!.toFixed(1)} ${c1[1]!.toFixed(1)} ${c2[0]!.toFixed(1)} ${c2[1]!.toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
}

const SUEZ = smooth([
  [4.4, 51.9],
  [1.5, 50.6],
  [-5.5, 48.6],
  [-10, 44],
  [-10, 38.5],
  [-6, 36],
  [3, 37.4],
  [14, 36.4],
  [24, 34.4],
  [32.3, 31.4],
  [32.6, 29.6],
  [35, 26.5],
  [38.5, 20],
  [42.4, 14.2],
  [44, 12.2],
  [51, 12.6],
  [62, 12],
  [76, 6.5],
  [80.6, 5.4],
  [92, 6],
  [98.5, 4],
  [103.8, 1.2],
  [107.5, 7],
  [112.5, 14.5],
  [118, 22.2],
  [121.6, 31],
]);
const CAPE = smooth([
  [4.4, 51.9],
  [-5.5, 48.6],
  [-13, 43],
  [-19, 30],
  [-21, 17],
  [-14, 3],
  [0, -8],
  [8, -22],
  [16, -33],
  [18.4, -35.2],
  [25, -37],
  [40, -33.5],
  [55, -22],
  [70, -8],
  [86, -1],
  [97, 3.5],
  [103.8, 1.2],
]);
const GULF = smooth([
  [51, 12.6],
  [57, 17.5],
  [59.5, 22.8],
  [56.5, 26.2],
  [55, 25.1],
]);

const PORTS = [
  { code: "NLRTM", lon: 4.4, lat: 51.9, label: "end" },
  { code: "ESALG", lon: -5.45, lat: 36.13, label: "start" },
  { code: "GRPIR", lon: 23.6, lat: 37.9, label: "end" },
  { code: "EGPSD", lon: 32.3, lat: 31.26, label: "end", home: true },
  { code: "DJJIB", lon: 43.1, lat: 11.6, label: "start" },
  { code: "AEJEA", lon: 55.0, lat: 25.0, label: "end" },
  { code: "SGSIN", lon: 103.8, lat: 1.3, label: "start" },
  { code: "CNSHA", lon: 121.5, lat: 31.2, label: "start" },
  { code: "ZACPT", lon: 18.4, lat: -33.9, label: "end" },
] as const;

const VESSELS = [
  { path: SUEZ, dur: 46, begin: 0 },
  { path: SUEZ, dur: 46, begin: -17 },
  { path: SUEZ, dur: 46, begin: -33, reverse: true },
  { path: CAPE, dur: 70, begin: -12 },
  { path: CAPE, dur: 70, begin: -48, reverse: true },
  { path: GULF, dur: 18, begin: -6 },
];

export function LaneMap({ className }: { className?: string }) {
  return (
    <MotionGuard className={className}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-full w-full"
        role="img"
        aria-label="PortPilot trade lanes: via Suez and via the Cape of Good Hope"
      >
        <defs>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" />
          </filter>
          <radialGradient id="vessel" r="1">
            <stop offset="0" stopColor="#ffffff" />
            <stop offset="0.5" stopColor="var(--lane)" />
            <stop offset="1" stopColor="var(--lane)" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* faint graticule */}
        <g stroke="rgb(184 199 219 / 0.08)" strokeWidth="1">
          {[-30, -15, 0, 15, 30, 45, 60].map((lat) => (
            <line key={lat} x1="0" x2={W} y1={py(lat)} y2={py(lat)} />
          ))}
          {[-15, 0, 15, 30, 45, 60, 75, 90, 105, 120].map((lon) => (
            <line key={lon} y1="0" y2={H} x1={px(lon)} x2={px(lon)} />
          ))}
        </g>

        <path d={DOTS} stroke="rgb(184 199 219 / 0.5)" strokeWidth="3.6" strokeLinecap="round" fill="none" />

        {/* lanes: a blurred glow under a crisp line; the Cape lane dashed (the long way round) */}
        <path
          d={SUEZ}
          stroke="var(--lane-glow)"
          strokeWidth="6"
          fill="none"
          filter="url(#glow)"
          opacity="0.8"
        />
        <path
          d={SUEZ}
          stroke="var(--lane)"
          strokeWidth="1.8"
          fill="none"
          className="lane-draw"
          style={{ "--len": 1700 } as React.CSSProperties}
        />
        <path
          d={CAPE}
          stroke="var(--lane)"
          strokeWidth="2.2"
          fill="none"
          strokeDasharray="1 6"
          strokeLinecap="round"
          opacity="1"
        />
        <path d={GULF} stroke="var(--lane)" strokeWidth="1.2" fill="none" opacity="0.6" />

        {VESSELS.map((v, i) => (
          <circle key={i} r="5" fill="url(#vessel)">
            <animateMotion
              dur={`${v.dur}s`}
              begin={`${v.begin}s`}
              repeatCount="indefinite"
              path={v.path}
              keyPoints={"reverse" in v ? "1;0" : "0;1"}
              keyTimes="0;1"
              calcMode="linear"
            />
          </circle>
        ))}

        {PORTS.map((p) => {
          const x = px(p.lon);
          const y = py(p.lat);
          const home = "home" in p;
          return (
            <g key={p.code}>
              {home ? (
                <circle
                  cx={x}
                  cy={y}
                  r="6"
                  fill="none"
                  stroke="var(--lane)"
                  strokeWidth="1.5"
                  className="port-pulse"
                />
              ) : null}
              <circle
                cx={x}
                cy={y}
                r={home ? 4.5 : 3}
                fill={home ? "#ffffff" : "var(--lane)"}
                stroke="var(--navy-deep)"
                strokeWidth="1.5"
              />
              <text
                x={p.label === "end" ? x + 8 : x - 8}
                y={y + 4}
                textAnchor={p.label === "end" ? "start" : "end"}
                className="fill-on-navy-muted font-mono"
                fontSize="12"
                fontWeight={home ? 700 : 500}
              >
                {p.code}
              </text>
            </g>
          );
        })}
      </svg>
    </MotionGuard>
  );
}
