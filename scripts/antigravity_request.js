/**
 * Antigravity Request Sanitizer for Shadowrocket
 * Strips incompatible consumer request fields (entitlement, project: aicode-consumers)
 * that cause Cloud Code API to return 400 Bad Request.
 */
let body = $request.body;
if (body) {
  try {
    let data = JSON.parse(body);
    let changed = false;
    if ("entitlement" in data) {
      delete data["entitlement"];
      changed = true;
    }
    if (data.project === "aicode-consumers" || data.project === "") {
      delete data["project"];
      changed = true;
    }
    if (changed) {
      body = JSON.stringify(data);
    }
  } catch (e) {
    // Binary or non-JSON body, pass untouched
  }
}
$done({ body: body });
