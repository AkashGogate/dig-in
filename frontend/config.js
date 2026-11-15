// Vercel rewrites /api to Fly, retaining browser Basic authentication. Local
// static serving uses port 8000. These are public addresses, never credentials.
const localDemo = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
window.DIG_IN_API = window.DIG_IN_API || window.KITCHEN_COPILOT_API || (localDemo ? `${location.protocol}//${location.hostname}:8000` : "");
window.KITCHEN_COPILOT_API = window.KITCHEN_COPILOT_API || window.DIG_IN_API;
// Streaming goes directly to the same Fly process as HTTP/Core. A short-lived,
// one-use ticket and device session authorize this connection, not a public key.
window.DIG_IN_VOICE_WS = window.DIG_IN_VOICE_WS || (localDemo ? `ws://${location.hostname}:8000/api/v2/voice/stream` : "wss://api.frictionless-kitchen.akashgogate.com/api/v2/voice/stream");
