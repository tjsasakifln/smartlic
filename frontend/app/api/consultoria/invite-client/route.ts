import { NextRequest, NextResponse } from "next/server";
import { getRefreshedToken } from "../../../../../lib/serverAuth";
const BACKEND_URL = process.env.BACKEND_URL;

export async function POST(request: NextRequest) {
  try {
    const t = await getRefreshedToken();
    const auth = t ? `Bearer ${t}` : request.headers.get("authorization");
    if (!auth || !auth.startsWith("Bearer ")) return NextResponse.json({ message: "Autenticacao necessaria." }, { status: 401 });
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/v1/consultoria/invite-client`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: auth }, body: JSON.stringify(body) });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch { return NextResponse.json({ message: "Erro ao convidar cliente." }, { status: 502 }); }
}
