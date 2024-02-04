import markdown2  # pyright: ignore[reportMissingTypeStubs]


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

    @property
    def html(self) -> str:
        return markdown2.markdown(  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            self.content
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "content": self.content,
        }
