from markdown2 import (  # pyright: ignore[reportMissingTypeStubs]
    markdown,  # pyright: ignore[reportUnknownVariableType]
)


class Recipe:
    def __init__(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:
        return f"<Recipe(text={self.text[:25]})>"

    def __str__(self) -> str:
        return self.text

    @property
    def html(self) -> str:
        return markdown(
            self.text, extras=["fences", "tables"]
        )  # pyright: ignore[reportUnknownVariableType]
