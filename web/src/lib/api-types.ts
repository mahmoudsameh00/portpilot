// The API's response shapes the shell needs, written from docs/api/openapi.json (Me, Products, Ready). Hand-written
// until F0 types every response and Orval generates the client (plan §7); keep them in step with the snapshot.
export type Products = {
  ask: boolean;
  packs_read: boolean;
  packs_decide: boolean;
  route_advice: boolean;
  voyage_watch: boolean;
  arrival_advice?: boolean;
  uploads: boolean;
};

export type Me = {
  employee_id: number;
  role: string;
  department: string;
  ceiling: number;
  tools: string[];
  products: Products;
};

export type Ready = {
  status: "ready" | "degraded";
  components: { name: string; ok: boolean }[];
  llm_requests_today: Record<string, number>;
};
