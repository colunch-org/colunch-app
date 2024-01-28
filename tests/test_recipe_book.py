import pytest

from domain.recipe_book import parse_part_description, parse_links


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
