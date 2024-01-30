import io

import pytest

from domain.recipe_book import (
    create_recipe_from_text_and_images,
    parse_part_description,
    parse_links,
)


def assert_recipe(recipe: str) -> None:
    kwords = ["ingredients", "instructions", "serves"]
    assert all(kword.lower() in recipe.lower() for kword in kwords)


@pytest.mark.parametrize(
    "description,expected",
    (
        (
            "https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita",
            ["https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita"],
        ),
        (
            (
                "Here is the link: "
                "https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita"
            ),
            ["https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita"],
        ),
        (
            (
                "Here is the link: "
                "https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita "
                "There are so many links "
                "https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita "
            ),
            [
                "https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita",
                "https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita",
            ],
        ),
        (
            "Bread and butter pudding.",
            [],
        ),
    ),
)
@pytest.mark.asyncio
async def test_parse_links(description: str, expected: list[str]) -> None:
    got = await parse_links(description)
    assert got == expected


@pytest.mark.asyncio
async def test_parse_part_description() -> None:
    given = (
        "Please remove all the text from this description pertaining to links. "
        "Respond only with the remaining text. "
        "Text: Meaty lasagne, don't use the béchamel though "
        "https://www.bbcgoodfood.com/recipes/lasagne"
    )
    exp = "Meaty lasagne, don't use the béchamel though"
    got = await parse_part_description(given)
    got = got[:-1] if got.endswith(".") else got
    assert got.lower() == exp.lower()


@pytest.mark.asyncio
async def test_create_recipe_from_text_and_images() -> None:
    description = "Bread and butter pudding."
    got = await create_recipe_from_text_and_images(description, [])
    assert_recipe(got)


@pytest.mark.asyncio
async def test_create_recipe_from_text_and_images_link() -> None:
    description = "https://www.bbcgoodfood.com/recipes/vegan-pizza-margherita"
    got = await create_recipe_from_text_and_images(description, [])
    assert_recipe(got)


@pytest.mark.asyncio
async def test_create_recipe_from_text_and_images_youtube() -> None:
    description = "https://www.youtube.com/watch?v=dG6UZu85AcQ"
    got = await create_recipe_from_text_and_images(description, [])
    assert_recipe(got)


@pytest.mark.asyncio
async def test_create_recipe_from_text_and_images_image() -> None:
    with open("tests/data/imgs/brownies.jpeg", "rb") as f:
        bites = io.BytesIO(f.read())
    got = await create_recipe_from_text_and_images("", [bites])
    assert_recipe(got)
