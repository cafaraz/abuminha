// അഡ്മിൻ ലോഗിൻ: GitHub-ൽ നിന്ന് തിരികെ വരുമ്പോൾ അഡ്മിൻ പാനലിന് ടോക്കൺ കൈമാറുന്നു
export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const saved = ((request.headers.get("Cookie") || "").match(/oauth_state=([^;]+)/) || [])[1];
  let status = "error";
  let content = { error: "ലോഗിൻ പരാജയപ്പെട്ടു. വീണ്ടും ശ്രമിക്കുക." };
  if (code && state && saved === state) {
    const r = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", "User-Agent": "abuminha-cms" },
      body: JSON.stringify({
        client_id: env.GITHUB_CLIENT_ID,
        client_secret: env.GITHUB_CLIENT_SECRET,
        code,
        redirect_uri: `${url.origin}/api/callback`,
      }),
    });
    const d = await r.json();
    if (d.access_token) {
      status = "success";
      content = { token: d.access_token, provider: "github" };
    } else if (d.error_description) {
      content = { error: d.error_description };
    }
  }
  const msg = JSON.stringify(`authorization:github:${status}:${JSON.stringify(content)}`).replace(/</g, "\\u003c");
  const origin = JSON.stringify(url.origin);
  const html = `<!doctype html><html><body><p>ലോഗിൻ ചെയ്യുന്നു…</p><script>
(function(){
  function receive(e){
    if(e.origin!==${origin})return;
    window.opener.postMessage(${msg}, e.origin);
    window.removeEventListener("message", receive);
  }
  window.addEventListener("message", receive);
  window.opener.postMessage("authorizing:github", ${origin});
})();
</script></body></html>`;
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Set-Cookie": "oauth_state=; Path=/api; Max-Age=0",
    },
  });
}
