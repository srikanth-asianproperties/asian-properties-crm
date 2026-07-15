/**
 * Cloudflare Pages Function: /api/snapshot
 *
 * Reads the "snapshot" key from the CLS_SNAPSHOT Workers KV binding
 * and returns it as JSON. The Cloudflare Access gate on cls.asianbuild.in
 * ensures only authenticated users (asianpropertygroups@gmail.com) ever
 * reach this endpoint — KV contents are never exposed publicly.
 *
 * KV binding name: CLS_SNAPSHOT
 * (configured in the cls-command-center Pages project settings)
 */
export async function onRequest(context) {
  const { env } = context;

  // Verify the KV binding exists — catches misconfiguration early
  if (!env.CLS_SNAPSHOT) {
    return new Response(
      JSON.stringify({ error: 'KV binding CLS_SNAPSHOT not found. Check Pages project settings.' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }

  try {
    const value = await env.CLS_SNAPSHOT.get('snapshot');

    if (value === null) {
      return new Response(
        JSON.stringify({
          error: 'No snapshot found in KV yet.',
          hint: 'Run python cls_snapshot.py on the Windows machine to push the first snapshot.'
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response(value, {
      status: 200,
      headers: {
        'Content-Type'  : 'application/json; charset=utf-8',
        'Cache-Control' : 'no-store',    // always serve fresh from KV, never edge-cached
      },
    });

  } catch (err) {
    return new Response(
      JSON.stringify({ error: 'KV read failed', detail: String(err) }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
