/**
 * Session endpoint: stores the refresh token in an httpOnly cookie (§176)
 * and returns the access token for in-memory use. The refresh token is
 * never accessible to client-side JavaScript.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.RFUND_BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  const { refreshToken, logout } = await request.json().catch(() => ({}));

  if (logout) {
    const res = NextResponse.json({ ok: true });
    res.cookies.delete("rfund_refresh");
    return res;
  }

  if (typeof refreshToken !== "string" || !refreshToken) {
    return NextResponse.json({ error: "refreshToken required" }, { status: 400 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set("rfund_refresh", refreshToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 14, // 14 days
  });
  return res;
}
