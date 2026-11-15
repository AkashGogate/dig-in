import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import { demoAccess } from "../deployment-auth.mjs";

const env = { DEMO_AUTH_USER: "demo", DEMO_AUTH_PASS: "test:only" };
const req = (raw = "") => new Request("https://demo.example/", { headers: { authorization: raw } });
test("missing or partial deployment credentials fail closed", () => {
  for (const config of [{}, { DEMO_AUTH_USER: "demo" }, { DEMO_AUTH_PASS: "test" }]) {
    assert.equal(demoAccess(req(), config).status, 503);
  }
});
test("Basic challenge, malformed input, wrong and correct credentials", () => {
  for (const raw of ["", "Bearer test", "Basic !!!", "Basic ZGVtbw==", "Basic " + Buffer.from("demo:wrong").toString("base64")]) {
    const response = demoAccess(req(raw), env);
    assert.equal(response.status, 401);
    assert.match(response.headers.get("www-authenticate"), /^Basic /);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
  assert.equal(demoAccess(req("Basic " + Buffer.from("demo:test:only").toString("base64")), env), null);
});
test("hosted API is same origin and voice connects to Fly; localhost stays local", () => {
  const source = readFileSync(new URL("../config.js", import.meta.url), "utf8");
  for (const [hostname, protocol, api] of [["demo.vercel.app", "https:", ""], ["localhost", "http:", "http://localhost:8000"]]) {
    const context = { location: { hostname, protocol }, window: {} };
    vm.runInNewContext(source, context);
    assert.equal(context.window.DIG_IN_API, api);
    assert.match(context.window.DIG_IN_VOICE_WS, /\/api\/v2\/voice\/stream$/);
    assert.equal(context.window.DIG_IN_VOICE_WS.startsWith("wss://api.frictionless-kitchen.akashgogate.com"), !api);
  }
});
test("actual Vercel entrypoint challenges and continues using Node runtime", async (t) => {
  const old = { user: process.env.DEMO_AUTH_USER, password: process.env.DEMO_AUTH_PASS };
  t.after(() => {
    for (const [name, value] of [["DEMO_AUTH_USER", old.user], ["DEMO_AUTH_PASS", old.password]]) {
      if (value === undefined) delete process.env[name]; else process.env[name] = value;
    }
  });
  process.env.DEMO_AUTH_USER = env.DEMO_AUTH_USER;
  process.env.DEMO_AUTH_PASS = env.DEMO_AUTH_PASS;
  const { default: middleware, config } = await import("../middleware.ts");
  assert.equal(config.runtime, "nodejs");
  assert.equal(middleware(req()).status, 401);
  assert.equal(middleware(req("Basic " + Buffer.from("demo:test:only").toString("base64"))).headers.get("x-middleware-next"), "1");
});
