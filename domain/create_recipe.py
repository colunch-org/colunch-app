"""The point."""

from app.domain.aopenai import Chat, ChatMsg, Content, ImgContent, TextContent
from app.domain.prompts import CreateRecipePrompt


async def create_recipe(text: list[str], imgs: list[str]) -> str:
    """Core functionality. Create a recipe from text and images."""

    text_content: list[Content] = [TextContent(t) for t in text]
    imgs_content: list[Content] = [ImgContent(i) for i in imgs]
    message = ChatMsg(role="user", content=text_content + imgs_content)

    chat = Chat.from_system_prompt(str(CreateRecipePrompt()))

    return await chat.chat(message)
