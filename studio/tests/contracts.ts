/** These rejected calls are compiler assertions; this file is never emitted. */
import { authorityText, decodeResponse } from "../src/transport.js";
import type { AuthorityText, ConstructionPayload, Fingerprint, RequestByRoute, ResponseFor, Route } from "../src/transport.js";

declare function submit<K extends Route>(route: K, payload: RequestByRoute[K]): Promise<ResponseFor<K>>;
declare const inspected: ConstructionPayload;
declare const fingerprint: Fingerprint;
const raw = authorityText('{"integer":9007199254740993,"float":1.0}');
void submit("/api/compile", { request_json: raw });
void submit("/api/construction/save", { ...inspected, expected_build_fingerprint: fingerprint });
// @ts-expect-error Parsed objects are display data, not transport authority.
void submit("/api/compile", { request_json: { source: "parsed" } });
// @ts-expect-error Ordinary strings require an explicit raw-authority boundary.
const authority: AuthorityText = "{}";
void authority;
// @ts-expect-error Saving requires the identity from the inspected snapshot.
void submit("/api/construction/save", inspected);
// @ts-expect-error Arbitrary strings cannot masquerade as inspected identities.
void submit("/api/construction/save", { ...inspected, expected_build_fingerprint: "invented" });
// @ts-expect-error Routes bind their own request shape.
void submit("/api/export", { request_json: raw });
// @ts-expect-error A display result does not have raw emitted build authority.
void decodeResponse("/api/construction/inspect", {}).record_json;
