class Recipe:
    def __init__(
        self,
        *,
        id: str,
        name: str,
        summary: str,
        content: str,
    ) -> None:
        self.id = id
        self.name = name
        self.summary = summary
        self.content = content

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "content": self.content,
        }
