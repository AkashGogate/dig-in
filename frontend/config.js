// Local demo defaults to the machine serving this page, port 8000. To use a
// shared backend, set DIG_IN_API to its reachable http(s)://host:port here.
// This config contains no keys. Paid credentials belong only on the backend.
window.DIG_IN_API = window.DIG_IN_API || window.KITCHEN_COPILOT_API || `${location.protocol}//${location.hostname || "localhost"}:8000`;
window.KITCHEN_COPILOT_API = window.KITCHEN_COPILOT_API || window.DIG_IN_API;
