/**
 * GraphQL BFF proxy (spec §5, §114): the browser only ever talks to its own
 * origin via relative paths. Secrets (Paystack keys, DATABASE_URL) never
 * reach the frontend; only public configuration is exposed.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.RFUND_BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Forwarded-For":
        request.headers.get("x-forwarded-for") ||
        request.headers.get("x-real-ip") ||
        "127.0.0.1",
    };
    const auth = request.headers.get("authorization");
    if (auth) headers["Authorization"] = auth;
    const device = request.headers.get("x-device-id");
    if (device) headers["X-Device-ID"] = device;

    const upstream = await fetch(`${BACKEND}/graphql`, {
      method: "POST",
      headers,
      body,
      signal: AbortSignal.timeout(30_000),
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[graphql-proxy] upstream failed", error);
    return NextResponse.json(
      {
        errors: [
          {
            message:
              "RFUND is not reachable right now. Please check your connection and try again.",
            extensions: { code: "NETWORK_UNAVAILABLE" },
          },
        ],
      },
      { status: 502 }
    );
  }
}
