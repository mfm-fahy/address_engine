import json

from fastapi import APIRouter, HTTPException

from ai.models import ChatRequest, ChatResponse, BusinessInsights
from ai.agent import get_agent
from ai.mcp_client import get_mcp_client

ai_router = APIRouter(prefix="/api/ai", tags=["ai"])
business_router = APIRouter(prefix="/api", tags=["business"])


@ai_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    agent = get_agent()
    return await agent.process_message(request.message)


@business_router.get("/business/insights", response_model=BusinessInsights)
async def business_insights():
    mcp = get_mcp_client()
    await mcp.discover_tools()

    stats_result = await mcp.read_resource("customers://stats")
    if not stats_result.get("success"):
        raise HTTPException(503, detail="Unable to fetch business statistics")

    alerts_result = await mcp.read_resource("alerts://list")

    agent = get_agent()
    prompt = (
        "Provide a concise business intelligence summary covering:\n"
        "1. Key metrics from the dashboard statistics\n"
        "2. Notable alerts or issues\n"
        "3. Strategic recommendations\n"
        f"Dashboard data: {json.dumps(stats_result.get('data', {}), default=str)}\n"
        f"Alerts data: {json.dumps(alerts_result.get('data', {}), default=str)}"
    )
    result = await agent.process_message(prompt)
    return BusinessInsights(summary=result.reply, token_usage=result.token_usage)


@business_router.get("/business/recommendations", response_model=BusinessInsights)
async def business_recommendations():
    mcp = get_mcp_client()
    await mcp.discover_tools()
    recs_result = await mcp.read_resource("recommendations://list")

    if not recs_result.get("success"):
        raise HTTPException(503, detail="Unable to fetch recommendations")

    agent = get_agent()
    data = recs_result.get("data", [])
    if isinstance(data, list) and len(data) > 5:
        data = data[:5]

    prompt = (
        "Analyze the following active business recommendations and provide:\n"
        "1. A summary of the top priority items\n"
        "2. Key patterns or trends across recommendations\n"
        "3. Suggested actions for the business team\n"
        f"Recommendations data: {json.dumps(data, default=str)}"
    )
    result = await agent.process_message(prompt)
    return BusinessInsights(summary=result.reply, token_usage=result.token_usage)


@business_router.get("/customers/{customer_id}/insights", response_model=BusinessInsights)
async def customer_insights(customer_id: str):
    agent = get_agent()
    prompt = (
        f"Provide a detailed business intelligence analysis for customer {customer_id}. "
        f"Use the available tools to look up their profile, alerts, and recommendations. "
        f"Then synthesize a concise insight covering customer value, risks, opportunities, and suggested actions."
    )
    result = await agent.process_message(prompt)
    return BusinessInsights(summary=result.reply, token_usage=result.token_usage)
