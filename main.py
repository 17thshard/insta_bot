import os
import re
from collections import deque, defaultdict
from urllib.parse import urlencode

import aiohttp
from discord import Intents, Message, File, Embed
from discord.ext import commands
import tempfile


INSTAGRAM_TOKEN = os.getenv('INSTAGRAM_TOKEN')
assert INSTAGRAM_TOKEN

INSTAGRAM_API = "https://graph.facebook.com/v10.0/instagram_oembed"

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
assert DISCORD_TOKEN
INSTAGRAM_RE = re.compile(r'(https?://www.instagram.com/p/[\w-]+[/\s$])')

intents = Intents.default()
intents.messages = True

bot = commands.Bot(command_prefix='ą', intents=intents)

LINK_TO_MESSAGE = {}
MESSAGE_TO_MESSAGE = defaultdict(list)
LINK_QUEUE = deque()
MESSAGE_QUEUE = deque()

QUEUE_SIZES = 5000


def clean_queues():
    while len(LINK_QUEUE) > QUEUE_SIZES:
        link = LINK_QUEUE.pop()
        if link in LINK_TO_MESSAGE:
            del LINK_TO_MESSAGE[link]
    while len(MESSAGE_QUEUE) > QUEUE_SIZES:
        msg_id = MESSAGE_QUEUE.pop()
        if msg_id in MESSAGE_TO_MESSAGE:
            del MESSAGE_TO_MESSAGE[msg_id]


def is_spoiler(message_text: str, link: str) -> bool:
    """
    Finds the given link in the message and tells if it's inside spoiler tag or not.
    """
    link_pos = message_text.find(link)
    spoiler_tags_count = message_text[:link_pos].count('||')
    return spoiler_tags_count % 2 == 1


def create_embed(link: str, insta_data: dict):
    embed = Embed()
    embed.type = "rich"
    embed.url = link
    embed.description = "Click on the username above to see this image (and possibly more!) on their Instagram profile."
    embed.title = insta_data['author_name']
    # embed.set_author(name=insta_data['author_name'])
    embed.set_image(url=insta_data['thumbnail_url'])
    # embed.set_thumbnail(url=insta_data['thumbnail_url'])
    embed.set_footer(text="Instagram embeds on Discord are broken, but I'll see what I can do.",
                     icon_url="https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png")
    return embed


async def process_message_link(message: Message, link: str):
    params = {
        'url': link,
        'maxwidth': 800,
        'fields': 'thumbnail_url,author_name,thumbnail_width,thumbnail_height',
    }
    headers = {
        'Authorization': f"Bearer {INSTAGRAM_TOKEN}"
    }
    async with message.channel.typing():
        async with aiohttp.ClientSession() as session:
            async with session.get(INSTAGRAM_API + '?' + urlencode(params), headers=headers,
                                   allow_redirects=True) as resp:
                insta_data = await resp.json()
            if is_spoiler(message.content, link):
                async with session.get(insta_data['thumbnail_url']) as img:
                    img = await img.read()
                with tempfile.NamedTemporaryFile(mode='rb+', prefix='SPOILER_', suffix='.jpg') as tmp_file:
                    tmp_file.write(img)
                    tmp_file.seek(0)
                    discord_file = File(tmp_file.name)
                    sent_message = await message.channel.send(
                                    content=f'Visit <{link}> to see this image '
                                            f'(and possibly more!) on authors Instagram page.',
                                    file=discord_file,
                                    reference=message, mention_author=False)
            else:
                sent_message = await message.channel.send(embed=create_embed(link, insta_data),
                                                          reference=message, mention_author=False)

            LINK_TO_MESSAGE[link] = sent_message
            MESSAGE_TO_MESSAGE[message.id].append(sent_message)
            LINK_QUEUE.appendleft(link)


@bot.event
async def on_message_edit(before: Message, after: Message):
    before_links = INSTAGRAM_RE.findall(before.content)
    after_links = INSTAGRAM_RE.findall(after.content)

    # Removed links
    for removed_link in set(before_links).difference(after_links):
        await LINK_TO_MESSAGE[removed_link].delete()
        del LINK_TO_MESSAGE[removed_link]

    # Added links
    for new_link in set(after_links).difference(before_links):
        await process_message_link(after, new_link)

    # Got embeds
    if after.embeds:
        for msg in MESSAGE_TO_MESSAGE[after.id]:
            await msg.delete()


@bot.event
async def on_message_delete(message: Message):
    try:
        for msg in MESSAGE_TO_MESSAGE[message.id]:
            await msg.delete()
    except KeyError:
        pass
    else:
        del MESSAGE_TO_MESSAGE[message.id]
        MESSAGE_QUEUE.remove(message.id)


@bot.event
async def on_message(message: Message):
    if message.author.id == bot.user.id:
        return

    if message.embeds:
        return

    for link in INSTAGRAM_RE.findall(message.content):
        await process_message_link(message, link)
        MESSAGE_QUEUE.appendleft(message.id)


if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
