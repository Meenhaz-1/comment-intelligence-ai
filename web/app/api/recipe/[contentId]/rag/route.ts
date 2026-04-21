import { NextResponse } from "next/server";

import { getRecipeDetail } from "@/lib/data/recipe-master";
import { buildRagAnswer } from "@/lib/server/rag";
import { RagQueryType } from "@/lib/types";
import { isRagReady } from "@/lib/utils/editorial";

type RouteContext = {
  params: Promise<{ contentId: string }>;
};

type RagRequestBody = {
  queryType?: RagQueryType;
  question?: string;
};

const VALID_QUERY_TYPES = new Set<RagQueryType>(["issue", "fix", "mixed", "editorial"]);

export async function POST(request: Request, context: RouteContext) {
  const { contentId } = await context.params;
  const detail = getRecipeDetail(contentId);

  if (!detail) {
    return NextResponse.json({ error: "Recipe not found." }, { status: 404 });
  }

  if (!detail.recipe.llmReadiness) {
    return NextResponse.json({ error: "RAG is unavailable for this recipe." }, { status: 400 });
  }

  if (!isRagReady(detail.recipe)) {
    return NextResponse.json(
      { error: "Limited evidence available for deeper analysis. Review the supporting comments directly." },
      { status: 409 },
    );
  }

  const body = (await request.json().catch(() => ({}))) as RagRequestBody;
  const queryType = body.queryType;
  const question = typeof body.question === "string" ? body.question : undefined;

  if (!queryType || !VALID_QUERY_TYPES.has(queryType)) {
    return NextResponse.json({ error: "Invalid query type." }, { status: 400 });
  }

  const answer = buildRagAnswer(detail.recipe, queryType, question);

  if (!answer) {
    return NextResponse.json(
      { error: "Not enough retrieved evidence to answer this question yet." },
      { status: 422 },
    );
  }

  return NextResponse.json(answer);
}
