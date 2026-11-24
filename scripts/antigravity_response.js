/**
 * Antigravity Response Patcher for Shadowrocket
 * Patches loadCodeAssist response:
 * 1. Clears ineligibleTiers (bypasses region/country ineligible restrictions)
 * 2. Sets usesGcpTos = false and userDefinedCloudaicompanionProject = false
 */
let body = $response.body;
if (body && $request.url && $request.url.indexOf("loadCodeAssist") !== -1) {
  try {
    let data = JSON.parse(body);
    data["ineligibleTiers"] = [];
    if (data.currentTier && typeof data.currentTier === "object") {
      data.currentTier["usesGcpTos"] = false;
      data.currentTier["userDefinedCloudaicompanionProject"] = false;
    }
    if (Array.isArray(data.allowedTiers)) {
      data.allowedTiers.forEach(function (t) {
        if (t && typeof t === "object") {
          t["usesGcpTos"] = false;
          t["userDefinedCloudaicompanionProject"] = false;
        }
      });
    }
    body = JSON.stringify(data);
  } catch (e) {
    // Non-JSON response, pass untouched
  }
}
$done({ body: body });
