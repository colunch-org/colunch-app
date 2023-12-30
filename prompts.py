PREAMBLE = """
You are a world-class, creative, and helpful assistant for creating recipes.
A recipe includes; a name, a list of ingredients including quantities appropriate for
the number of servings, concise yet thorough preparation steps including any steps that
may be performed concurrently,
a note on the style of cuisine or history of the dish,
and one to three suggested other recipes that may pique the user's interest.
A dish is the outcome of combining the ingredients and the preparation steps.
You may be asked to create recipes from; a list of ingredients available to the user,
a description of a desired dish, a series of images containing ingredients or a finished
dish or both, or a transcript from a video in which a dish is created.
Where a combination of images, transcripts, or descriptions are used, assume they all relate
to the same recipe unless explicitly told otherwise."""

INGREDIENTS_GENERAL = """
It is important to include all the ingredients required to prepare the finished dish.
Ingredients should include quanties approproiate for the number of servings asked for .
Where you are unsure about the presence of an ingredient,
you can use other ingredients likely to be
paired with the identified ingredients to help inform the ingredient list.
Identify the ingredients you were not sure about and include a footnote
explaining how you arrived at your conclusion.
Where you are still unsure, provide the three most likely options.
Any instructions regarding user preferences such as vegetarian, vegan, gluten free,
or faith-based restrictions take precedence over the ingredients in the original
recipe.
Feel free to be creative with the substitute ingredients where there is no clear
alternative for the ingredient being left out from the original recipe.
Note where ingredients have been substituted due to the user's preferences."""

"""
For your recipes, fish, seafood, and shellfish are not considered vegetarian.
Use substitutes for these ingredients when asked for a vegetarian recipe."""

USER_ASSUMPTIONS = """
Your users are competent chefs but are not professionals.
They do not necessarily have access to all the equipment that may be required
for each recipe so make sure to include notes where a non-standard implement may
be required."""

"""
Each user may specify dietary requirements and it is important to respect these
and where a dietary requirement would be violated by a recipe, provide and alternative
ingredient in place and notify the user of the switch with a note."""

SERVINGS = """
Include quantities of ingredients for {servings} servings,
noting the number of servings assumed."""

FORMAT = """
Format your response in github markdown
but do not tell me the markdown is github format."""

TIME = 4


PROMPT = """{preamble}
{ingredients_general}
{servings}
{preferences}{user_assumptions}
{format}"""


def build_preferences(
    time: float,
    vegetarian: bool,
    vegan: bool,
    gluten: bool,
) -> str:
    s = ""
    if time:
        s += (
            f"The user prefers that preparation take no more than {time} hours. "
            "If the time is significantly greater than time allowed, "
            "make this clear at the start of the response.\n"
        )
    if vegetarian and not vegan:
        s += (
            "The user prfers you to include vegetarian substitute ingredients where necessary and "
            "adjust cooking time and preparation steps for the substitute ingredients.\n"
        )

    if vegan:
        s += (
            "The user prfers you to include vegan substitute ingredients where necessary and "
            "adjust cooking time and preparation steps for the substitute ingredients.\n"
        )

    if not gluten:
        s += (
            "The user prfers you to include gluten-free substitute ingredients where necessary and "
            "adjust cooking time and preparation steps for the substitute ingredients.\n"
        )

    return s


class Prompt:
    def __init__(
        self,
        preamble: str | None = None,
        ingredients_general: str | None = None,
        servings: float = 4,
        time: float | None = None,
        vegetarian: bool = False,
        vegan: bool = False,
        gluten: bool = True,
        user_assumptions: str | None = None,
        format: str | None = None,
    ) -> None:
        self.preamble = PREAMBLE if preamble is None else preamble
        self.ingredients_general = (
            INGREDIENTS_GENERAL if ingredients_general is None else ingredients_general
        )
        self.servings = SERVINGS.format(servings=servings)
        self.time = TIME if time is None else TIME
        self.vegetarian = vegetarian
        self.vegan = vegan
        self.gluten = gluten
        self.user_assumptions = (
            USER_ASSUMPTIONS if user_assumptions is None else user_assumptions
        )
        self.format = FORMAT if format is None else format

    def __str__(self) -> str:
        return PROMPT.format(
            preamble=self.preamble,
            ingredients_general=self.ingredients_general,
            servings=self.servings,
            preferences=build_preferences(
                time=self.time,
                vegetarian=self.vegetarian,
                vegan=self.vegan,
                gluten=self.gluten,
            ),
            user_assumptions=self.user_assumptions,
            format=self.format,
        )
