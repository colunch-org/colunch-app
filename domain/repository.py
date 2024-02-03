import asyncio

import pinecone  # pyright: ignore[reportMissingTypeStubs]

from ajolt import AsyncJolt
from domain.models import Recipe


class RecipeVectorRepository:
    def __init__(
        self,
        *,
        client: pinecone.Pinecone | None = None,
        index_name: str = "recipes",
    ) -> None:
        self.client = pinecone.Pinecone() if client is None else client
        idx = self.client.Index(index_name)  # pyright: ignore[reportUnknownMemberType]
        if idx is None:
            raise ValueError
        self.idx = idx

    async def add(self, *, recipe: Recipe, vector: list[float]) -> None:
        async with AsyncJolt():
            await asyncio.to_thread(
                self.idx.upsert,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                vectors=[
                    {
                        "id": recipe.id,
                        "values": vector,
                        "metadata": recipe.to_dict(),
                    }
                ],
            )

    async def search(self, vector: list[float], *, n: int = 3) -> list[Recipe]:
        async with AsyncJolt():
            res = await asyncio.to_thread(
                self.idx.query,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                vector=vector,
                top_k=n,
                include_metadata=True,
            )

        return [m["metadata"] for m in res["matches"]]
