// Types of audit-gate.mjs, for the logic test.
export interface AuditException {
  id: string;
  package: string;
  reviewedLatest: string;
  until: string;
}

export const AUDIT_EXCEPTIONS: AuditException[];

export function blockingAdvisories(report: unknown): { id: string; package: string }[];

export function auditProblems(
  report: unknown,
  options: {
    exceptions?: AuditException[];
    today: string;
    latestOf: (name: string) => string | null;
  },
): string[];
