/**
 * Silent refresh: reads the httpOnly refresh cookie, rotates it through the
 * Django API, returns a fresh access token to the client (memory only).
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.RFUND_BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("rfund_refresh")?.value;
  if (!refreshToken) {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  try {
    const upstream = await fetch(`${BACKEND}/graphql`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: `
          mutation Refresh($token: String!) {
            refreshToken(refreshToken: $token) {
              accessToken
              refreshToken
              user { id phone firstName lastName }
            }
          }
        `,
        variables: { token: refreshToken },
      }),
      signal: AbortSignal.timeout(15_000),
    });
    const body = await upstream.json();
    if (body.errors?.length) {
      const res = NextResponse.json({ authenticated: false }, { status: 200 });
      res.cookies.delete("rfund_refresh");
      return res;
    }
    const pair = body.data?.refreshToken;
    if (!pair?.accessToken) {
      return NextResponse.json({ authenticated: false }, { status: 200 });
    }
    const res = NextResponse.json({
      authenticated: true,
      accessToken: pair.accessToken,
      user: pair.user,
    });
    if (pair.refreshToken) {
      res.cookies.set("rfund_refresh", pair.refreshToken, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: 60 * 60 * 24 * 14,
      });
    }
    return res;
  } catch (error) {
    console.error("[auth-refresh] upstream failed", error);
    return NextResponse.json(
      { authenticated: false, networkError: true },
      { status: 200 }
    );
  }
}
