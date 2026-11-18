import { next } from "@vercel/functions";
import { demoAccess } from "./deployment-auth.mjs";

export default function middleware(request: Request) {
  return demoAccess(request, process.env) ?? next();
}

// One gate covers everything: pages and API share the single Vercel sign-in,
// so the browser's cached Basic Auth also covers same-origin /api/* fetches
// and backend/app/demo_auth.py no longer needs a separate in-page login.
// /api/v2/menu/extract alone bypasses this gate (large uploads, authenticated on Fly itself).
export const config = { runtime: "nodejs", matcher: ["/((?!api/v2/menu/extract).*)"] };
