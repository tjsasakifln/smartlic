import { NextRequest, NextResponse } from "next/server";
import { getRefreshedToken } from "../../../../../lib/serverAuth";
const BACKEND_URL = process.env.BACKEND_URL;

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const t = await getRefreshedToken();
    const auth = t ? `Bearer ${t}` : request.headers.get("authorization");
    if (!auth || !auth.startsWith("Bearer ")) return NextResponse.json({ message: "Autenticacao necessaria." }, { status: 401 });
    const res = await fetch(`${BACKEND_URL}/v1/consultoria/shared/${id}`, { method: "GET", headers: { "Content-Type": "application/json", Authorization: auth } });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch { return NextResponse.json({ message: "Erro ao listar compartilhados." }, { status: 502 }); }
}
