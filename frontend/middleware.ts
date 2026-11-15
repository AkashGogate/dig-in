import { next } from "@vercel/functions";
import { demoAccess } from "./deployment-auth.mjs";

export default function middleware(request: Request) {
  return demoAccess(request, process.env) ?? next();
}

// Large menu uploads bypass middleware and are authenticated on Fly itself.
// All static pages/assets (including the legacy entry points) require sign-in.
export const config = { runtime: "nodejs", matcher: ["/((?!api/).*)"] };
