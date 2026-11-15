/** Server-only Vercel gate. Never import this module into browser assets. */
import { timingSafeEqual } from "node:crypto";

function equal(value, expected) {
  const a = Buffer.from(value);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function demoAccess(request, env) {
  const user = env.DEMO_AUTH_USER;
  const password = env.DEMO_AUTH_PASS;
  const headers = { "Cache-Control": "no-store" };
  if (!user || !password) {
    return new Response("Demo access is not configured.", { status: 503, headers });
  }
  const authorization = request.headers.get("authorization") || "";
  let valid = false;
  if (/^Basic /i.test(authorization)) {
    const encoded = authorization.slice(6);
    // Buffer decoding is permissive; reject malformed Base64 before decoding.
    if (/^[A-Za-z0-9+/]+={0,2}$/.test(encoded) && encoded.length % 4 === 0) {
      const raw = Buffer.from(encoded, "base64").toString("utf8");
      const separator = raw.indexOf(":");
      if (separator >= 0) {
        valid = equal(raw.slice(0, separator), user) & equal(raw.slice(separator + 1), password);
      }
    }
  }
  if (valid) return null;
  return new Response("Demo sign-in required.", {
    status: 401,
    headers: { ...headers, "WWW-Authenticate": 'Basic realm="Dig In demo"' },
  });
}
