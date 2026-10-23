import asyncio
from typing import Any, Awaitable, Callable, List, Optional, Sequence, Tuple, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import Document, Topic

T = TypeVar("T")


def plan_counts(topics: Sequence[T], total: int, size_of=lambda t: len(t.content.split())) -> List[Tuple[T, int]]:
    """
    Spreads `total` items (cards or questions) across topics so the overall count matches what the
    student asked for. Bigger topics get the leftovers; when there are more topics than items, only
    the biggest topics get one each. Returns (topic, count) pairs in the topics' original order.
    """
    if total <= 0 or not topics:
        return []
    by_size = sorted(range(len(topics)), key=lambda i: size_of(topics[i]), reverse=True)
    counts = [total // len(topics)] * len(topics)
    for i in by_size[: total % len(topics)]:
        counts[i] += 1
    return [(topic, n) for topic, n in zip(topics, counts) if n > 0]


async def run_per_topic(
    plan: List[Tuple[Topic, int]],
    generate: Callable[[Topic, int], Awaitable[List[Any]]],
    max_concurrent: int = 4,
) -> List[Tuple[Topic, int, List[Any]]]:
    """Runs one AI generation per topic in parallel (a few at a time) instead of one after another."""
    gate = asyncio.Semaphore(max_concurrent)

    async def one(topic: Topic, count: int):
        async with gate:
            return topic, count, await generate(topic, count)

    return list(await asyncio.gather(*(one(topic, count) for topic, count in plan)))


def topics_for_generation(db: Session, doc: Document, topic_id: Optional[int]) -> List[Topic]:
    """The topic the student picked, or every topic of the document (creating one if it has none)."""
    if topic_id:
        topic = db.query(Topic).filter(Topic.id == topic_id, Topic.document_id == doc.id).first()
        if not topic:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
        return [topic]

    topics = db.query(Topic).filter(Topic.document_id == doc.id).order_by(Topic.order_index).all()
    if not topics:
        topic = Topic(document_id=doc.id, title="General", content=doc.raw_text, order_index=0)
        db.add(topic)
        db.commit()
        db.refresh(topic)
        topics = [topic]
    return topics
