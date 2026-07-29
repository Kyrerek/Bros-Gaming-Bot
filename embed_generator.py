import discord
from field import Field


def custom_embed(
    title: str,
    image: str = None,
    description: str = None,
    color: discord.Color = None,
    fields: list[Field] = None,
) -> discord.Embed:
    e = discord.Embed(title=title)

    if image:
        e.set_image(url=image)

    if description:
        e.description = description

    if color:
        # TypeError
        e.color = color

    if fields:
        for f in fields:
            name = f.name
            value = f.value
            inline = f.inline
            e.add_field(name=name, value=value, inline=inline)

    return e


def success_embed(description: str = None) -> discord.Embed:
    e = discord.Embed(
        title="Success ✅",
        description="Everything went good c:",
        color=discord.Color.green(),
    )
    e.set_image(
        url="https://bluemoji.io/cdn-proxy/646218c67da47160c64a84d5/66b3e5d0c2ab246786ca1d5e_86.png"
    )
    if description:
        e.description = description
    return e


def error_embed(description: str = None) -> discord.Embed:
    e = discord.Embed(
        title="Error ❌",
        description="Something went wrong :c",
        color=discord.Color.red(),
    )
    e.set_image(
        url="https://bluemoji.io/cdn-proxy/646218c67da47160c64a84d5/698d0c11601115d9bc83b568_102.png"
    )
    if description:
        e.description = description
    return e
