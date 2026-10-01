/** Syntactic display/transport contracts. Only the server checks artifact meaning. */
declare const authorityBrand: unique symbol;
export type AuthorityText = string & { readonly [authorityBrand]: true };
declare const fingerprintBrand: unique symbol;
export type Fingerprint = string & { readonly [fingerprintBrand]: true };

type Decoder<T> = (value: unknown) => T;
type Shape = Record<string, Decoder<unknown>>;
type Decoded<S extends Shape> = { [K in keyof S]: ReturnType<S[K]> };
const invalid = (): never => { throw new Error("The server returned an invalid Studio response. Reload the studio and try again."); };
const string: Decoder<string> = value => typeof value === "string" ? value : invalid();
const number: Decoder<number> = value => typeof value === "number" && Number.isFinite(value) ? value : invalid();
const boolean: Decoder<boolean> = value => typeof value === "boolean" ? value : invalid();
const unknown: Decoder<unknown> = value => value;
export const authorityText: Decoder<AuthorityText> = value => string(value) as AuthorityText;
const fingerprint: Decoder<Fingerprint> = value => string(value) as Fingerprint;
const nullable = <T>(decode: Decoder<T>): Decoder<T | null> => value => value === null ? null : decode(value);
const optional = <T>(decode: Decoder<T>): Decoder<T | undefined> => value => value === undefined ? undefined : decode(value);
const array = <T>(decode: Decoder<T>): Decoder<T[]> => value => Array.isArray(value) ? value.map(decode) : invalid();
function object<S extends Shape>(shape: S): Decoder<Decoded<S>> {
  return value => {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid();
    const record = value as Record<string, unknown>;
    for (const [key, decode] of Object.entries(shape)) decode(record[key]);
    // The preceding shape check covers every declared field. Keep additional
    // display fields intact; do not normalize any authority or artifact object.
    return record as Decoded<S>;
  };
}
const artifactObject = object({});

const overview = object({
  cell_type: string, target_name: string, cue: string, product: string,
  source_summary: string, library_name: string, constraints_json: string,
  fixture: boolean, constraints: object({ preference: string }),
  product_options: array(object({ id: string, label: string, protein: string })),
});
export type Overview = ReturnType<typeof overview>;
const prepared = object({ request: artifactObject, request_json: authorityText, overview });
export type PreparedRequest = ReturnType<typeof prepared>;
const part = object({ id: string, kind: string, start: number, end: number });
export type Part = ReturnType<typeof part>;
const check = object({ stage: string, outcome: string, detail: unknown });
export type Check = ReturnType<typeof check>;
const alternative = object({
  architecture_id: string, cds_part_id: string, length_nt: number, selected: boolean,
  rejections: array(object({ code: string, message: string })),
});
export type Alternative = ReturnType<typeof alternative>;
const summary = object({
  sequence: nullable(string), length_nt: nullable(number), protein: nullable(string),
  architecture: nullable(string), parts: array(part), checks: array(check),
  alternatives: array(alternative),
  unresolved: array(object({ id: string, description: string })),
  build_fingerprint: fingerprint, scope: string, therapeutic_implementation: string,
  human_therapeutic_admission: string,
});
export type CandidateSummary = ReturnType<typeof summary>;
const compiled = object({
  request: artifactObject, request_json: authorityText, record: artifactObject,
  record_json: authorityText, summary,
});
const session = object({ token: string, version: string, example: prepared });
const exported = object({ content: string, mime_type: string, filename: string });
const assessment = object({ outcome: string, diagnostics: array(string) });
const review = object({
  sources: object({
    status: string,
    readiness: nullable(object({ metadata_consistency: string, diagnostics: array(string),
      cases: array(object({ case_id: string, fields: array(object({
        field: string, availability: string, note: string,
      })) })),
    })),
  }),
  bindings: object({
    assessment: nullable(assessment), bindings: array(object({
      requirement_id: string, source_kind: string, source_id: string,
      construction_requirement_id: string, role_id: string,
    })),
  }),
  evidence: object({
    status: string, dependencies: optional(array(object({ id: string, status: string }))),
    sources: array(object({ id: string, kind: string, use: string,
      observations: array(object({ requirement_id: string, observation_id: string })),
    })),
  }),
});
export type ConstructionReview = ReturnType<typeof review>;
const inspection = object({
  build_fingerprint: fingerprint, stored_assessment: assessment,
  freshness: object({ assessment: nullable(assessment) }),
  molecules: array(object({ id: string, form: string,
    space: object({ alphabet: string, topology: string, length: number }),
  })),
  request: object({ required_members: array(object({
    id: string, category: string, member_id: nullable(string), external_id: nullable(string),
    roles: array(object({ role: string, compartment: string })),
  })) }),
  missing_members: array(string), construction_diagnostics: array(string),
  roots: unknown, steps: unknown, values: unknown, complexes: unknown, amounts: unknown,
  claims: unknown, review,
});
export type ConstructionInspection = ReturnType<typeof inspection>;
const saved = object({ build_json: authorityText, build_fingerprint: fingerprint });

export type ExportFormat = "fasta" | "build" | "request";
export interface ExampleControls { product: string; architecture: string; max_length: number | null }
export interface ConstructionPayload {
  build_json: AuthorityText;
  expected_request_json: AuthorityText | null;
  review: {
    source_inventory_json: AuthorityText | null;
    binding_request_json: AuthorityText | null;
    evidence_request_json: AuthorityText | null;
    evidence_receipt_json: AuthorityText | null;
  };
}
export interface RequestByRoute {
  "/api/session": undefined;
  "/api/prepare": { example: ExampleControls } | { request_json: AuthorityText };
  "/api/compile": { request_json: AuthorityText };
  "/api/export": { request_json: AuthorityText; record_json: AuthorityText; format: ExportFormat };
  "/api/construction/inspect": ConstructionPayload;
  "/api/construction/save": ConstructionPayload & { expected_build_fingerprint: Fingerprint };
}
const decoders = {
  "/api/session": session,
  "/api/prepare": prepared,
  "/api/compile": compiled,
  "/api/export": exported,
  "/api/construction/inspect": inspection,
  "/api/construction/save": saved,
};
export type Route = keyof RequestByRoute;
export type ResponseFor<K extends Route> = ReturnType<(typeof decoders)[K]>;

export class StudioError extends Error {
  readonly code: string | undefined;
  readonly details: unknown;
  constructor(message: string, code?: string, details?: unknown) {
    super(message); this.name = "StudioError"; this.code = code; this.details = details;
  }
}
const envelope = object({ ok: boolean, result: optional(unknown), error: optional(object({
  message: optional(string), code: optional(string), details: optional(unknown),
})) });
export function decodeResponse<K extends Route>(route: K, value: unknown, status = 200): ResponseFor<K> {
  const decoded = envelope(value);
  if (status < 200 || status >= 300 || !decoded.ok) {
    throw new StudioError(decoded.error?.message || `The local compiler returned HTTP ${status}.`,
      decoded.error?.code, decoded.error?.details);
  }
  // TypeScript loses the key/result relation when indexing a function union.
  // Each decoder is statically paired with its route and validates at runtime.
  return decoders[route](decoded.result) as ResponseFor<K>;
}
export function errorInfo(value: unknown): { name: string; message: string; code?: string; details?: unknown } {
  if (value instanceof StudioError) return {
    name: value.name, message: value.message, ...(value.code === undefined ? {} : { code: value.code }), details: value.details,
  };
  return value instanceof Error ? value : { name: "Error", message: String(value) };
}
export function element<K extends keyof HTMLElementTagNameMap>(id: string, tag: K): HTMLElementTagNameMap[K] {
  const result = document.getElementById(id);
  if (!result || result.localName !== tag) throw new Error(`Studio requires ${tag}#${id}.`);
  return result as HTMLElementTagNameMap[K];
}
export function exportFormat(value: unknown): ExportFormat {
  if (value === "fasta" || value === "build" || value === "request") return value;
  throw new Error("Unknown Studio export format.");
}
