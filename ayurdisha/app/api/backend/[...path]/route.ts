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
      },
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
    });
    return new Response(await res.text(), {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "application/json",
      },
    });
  } catch {
    return Response.json(
      { detail: `Backend unreachable at ${BACKEND_URL}` },
      { status: 502 },
    );
  }
}

export { proxy as GET, proxy as POST };
