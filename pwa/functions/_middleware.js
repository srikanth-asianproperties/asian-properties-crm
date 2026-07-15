/**
 * Cloudflare Pages Middleware
 * Runs on every request before static assets are served.
 * Routes /api/* to the appropriate function handler.
 * This ensures /api/snapshot is never intercepted by the
 * static asset fallback (which would serve index.html).
 */
export async function onRequest(context) {
  const url = new URL(context.request.url);

  // Only intercept /api/snapshot — pass everything else through
  if (url.pathname === '/api/snapshot') {
    const { env } = context;

    if (!env.CLS_SNAPSHOT) {
      return new Response(
        JSON.stringify({ error: 'KV binding CLS_SNAPSHOT not configured.' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    try {
      const value = await env.CLS_SNAPSHOT.get('snapshot');
      if (value === null) {
        return new Response(
          JSON.stringify({ error: 'No snapshot in KV yet. Run cls_snapshot.py first.' }),
          { status: 404, headers: { 'Content-Type': 'application/json' } }
        );
      }
      return new Response(value, {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      });
    } catch (err) {
      return new Response(
        JSON.stringify({ error: 'KV read failed', detail: String(err) }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }
  }

  // All other requests: serve normally (static assets, index.html, etc.)
  return context.next();
}
