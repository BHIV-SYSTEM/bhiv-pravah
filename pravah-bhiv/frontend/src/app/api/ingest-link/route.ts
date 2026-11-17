import { NextResponse } from 'next/server';
import crypto from 'crypto';

const DECISION_BRAIN_URL =
  process.env.DECISION_BRAIN_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_DECISION_BRAIN_URL ||
  'http://localhost:8010';

function generateInternalToken(): string {
  const secret = process.env.JWT_SECRET_KEY || 'default-jwt-secret-change-in-prod';
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  const payload = Buffer.from(
    JSON.stringify({
      user_id: 'pravah_operator_ui',
      iat: now,
      exp: now + 3600,
    })
  ).toString('base64url');
  const signature = crypto
    .createHmac('sha256', secret)
    .update(`${header}.${payload}`)
    .digest('base64url');
  return `${header}.${payload}.${signature}`;
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const link = body?.link;

    if (!link || typeof link !== 'string' || !link.trim()) {
      return NextResponse.json(
        { success: false, error: 'A valid repository or website URL is required.' },
        { status: 400 }
      );
    }

    const token = generateInternalToken();
    const targetUrl = `${DECISION_BRAIN_URL.replace(/\/+$/, '')}/ingest-link`;

    const res = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ link: link.trim() }),
    });

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      const errorMsg = data?.detail || data?.error || `Backend returned HTTP ${res.status}`;
      return NextResponse.json({ success: false, error: errorMsg }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: `Internal proxy error connecting to Decision Brain: ${String(error)}`,
      },
      { status: 500 }
    );
  }
}
