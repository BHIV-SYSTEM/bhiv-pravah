import { NextResponse } from 'next/server';

const GROUP2_URL =
  process.env.NEXT_PUBLIC_VANA_GROUP2_URL || 'https://niyantran.blackholeinfiverse.com/api/group2/context/resolve';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    
    const res = await fetch(GROUP2_URL, {
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
        { error: `Group 2 API Error: ${data}` },
        { status: res.status }
      );
    }
    
    // Attempt to parse JSON response
    let jsonResp;
    try {
      jsonResp = JSON.parse(data);
    } catch {
      return NextResponse.json({ error: 'Invalid JSON response from Group 2', raw: data }, { status: 500 });
    }

    return NextResponse.json(jsonResp);
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal Server Error while proxying to Group 2', details: String(error) },
      { status: 500 }
    );
  }
}
