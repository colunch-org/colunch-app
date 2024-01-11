from jinja2 import Environment
from markupsafe import Markup

from app.domain.models import Recipe


recipe_detail = TEMPLATES.get_template("recipe-detail.html")


class RecipeDetail:
    def __init__(
        self,
        recipe: Recipe,
        *,
        environment: Environment,
        template_name: str = "recipe-detail.html",
    ) -> None:
        self.recipe = recipe
        self.env = environment
        self.name = template_name

    def html(self) -> str:
        return self.env.get_template(self.name).render(
            title=self.recipe.name,
            text=Markup(recipe.html),
        )
