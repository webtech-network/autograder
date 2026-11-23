"""``GET /metrics``: Prometheus exposition of this service (public, like health; never route it publicly).

It carries counts, durations and closed-set labels only (see ``web/metrics.py``),
so it needs no credential; the deployment keeps it on the private network.
"""
import asyncio

from fastapi import APIRouter, Depends

from sandbox_manager.metrics import exposition
from web.api.deps import get_host

router = APIRouter(tags=["Metrics"])


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics(host=Depends(get_host)):
    await host.metrics.queue.refresh(host.sessions)
    # Collectors read pool state under locks: keep that off the event loop.
    return await asyncio.to_thread(exposition, host.metrics.registry)
