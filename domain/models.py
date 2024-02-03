class Recipe:
    def __init__(
        self,
        name: str,
        summary: str,
        ingredients: tuple[str, ...],
        instructions: tuple[str, ...],
    ) -> None:
        self.name = name
        self.summary = summary
        self.ingredients = ingredients
        self.instructions = instructions

    def __repr__(self) -> str:
        return f"<Recipe(name={self.name}, summary={self.summary})>"

    def __str__(self) -> str:
        return self.name
