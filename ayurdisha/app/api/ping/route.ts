import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const BACKEND_URL =
    process.env.AYURDISHA_API_URL ||
    (process.env.NODE_ENV === "production"
      ? "https://ayurdisha.onrender.com"
      : "http://127.0.0.1:8000");

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    const res = await fetch(`${BACKEND_URL}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      return NextResponse.json({ status: "ok" });
    }
    return NextResponse.json({ status: "error" }, { status: 502 });
  } catch {
    return NextResponse.json({ status: "waking" }, { status: 503 });
  }
}
