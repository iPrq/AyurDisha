import type { NextRequest } from "next/server";

const BACKEND_URL = process.env.AYURDISHA_API_URL ?? "http://127.0.0.1:8000";

export const maxDuration = 300;

async function proxy(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const url = `${BACKEND_URL}/${path.join("/")}${req.nextUrl.search}`;
  try {
    const hasBody = req.method !== "GET" && req.method !== "HEAD";
    const res = await fetch(url, {
      method: req.method,
      headers: {
        "Content-Type": req.headers.get("content-type") ?? "application/json",
        Accept: req.headers.get("accept") ?? "*/*",
      },
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
      signal: req.signal,
    });
    const contentType = res.headers.get("Content-Type") ?? "application/json";
    if (contentType.startsWith("text/event-stream") && res.body) {
      return new Response(res.body, {
        status: res.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-transform",
          "X-Accel-Buffering": "no",
        },
      });
    }
    return new Response(await res.arrayBuffer(), {
      status: res.status,
      headers: { "Content-Type": contentType },
    });
  } catch {
    return Response.json(
      { detail: `Backend unreachable at ${BACKEND_URL}` },
      { status: 502 },
    );
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
