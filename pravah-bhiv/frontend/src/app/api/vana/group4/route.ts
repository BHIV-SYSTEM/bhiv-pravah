import { NextResponse } from 'next/server';

function getGroup4VanaUrl(): { url?: string; error?: string } {
  const envUrl = process.env.VANA_GROUP4_URL;
  const isProd = process.env.NODE_ENV === 'production' || process.env.ENVIRONMENT === 'prod';

  if (!envUrl && isProd) {
    return { error: 'Configuration Error: VANA_GROUP4_URL must be explicitly configured in production' };
  }

  return { url: envUrl || 'http://localhost:8010' };
}

export async function POST(request: Request) {
  try {
    const { url: upstreamUrl, error: configError } = getGroup4VanaUrl();
    if (configError || !upstreamUrl) {
      return NextResponse.json(
        { error: configError || 'VANA upstream URL unconfigured' },
        { status: 500 }
      );
    }

    const body = await request.json();

    const res = await fetch(`${upstreamUrl}/vana/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await res.text();

    if (!res.ok) {
      return NextResponse.json(
        { error: `Group 4 API Error: ${data}` },
        { status: res.status }
      );
    }

    // Attempt to parse JSON response
    let jsonResp;
    try {
      jsonResp = JSON.parse(data);
    } catch {
      return NextResponse.json({ error: 'Invalid JSON response from Group 4', raw: data }, { status: 500 });
    }

    return NextResponse.json(jsonResp);
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal Server Error while proxying to Group 4', details: String(error) },
      { status: 500 }
    );
  }
}
