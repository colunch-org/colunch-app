from markdown2 import (  # pyright: ignore[reportMissingTypeStubs]
    markdown,  # pyright: ignore[reportUnknownVariableType]
)


class Recipe:
    def __init__(self, id: str, name: str, text: str) -> None:
        self.id = id
        self.name = name
        self.text = text

    def __repr__(self) -> str:
        return f"<Recipe(id={self.id}, name={self.name})>"

    def __str__(self) -> str:
        return self.text

    @property
    def html(self) -> str:
        return markdown(
            self.text, extras=["fences", "tables"]
        )  # pyright: ignore[reportUnknownVariableType]
