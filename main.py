# Copyright 2021 Mestiv
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import re
import tempfile
from collections import defaultdict, deque

import aiohttp
import hikari
import hikari.embeds
import hikari.files
from instascrape import Post

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
assert DISCORD_TOKEN
INSTAGRAM_RE = re.compile(r'(https?://www.instagram.com/p/[\w-]+[/\s$])')

INSTA_SESSION_ID = os.getenv('INSTA_SESSION_ID')
assert INSTA_SESSION_ID
HEADERS = {"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
           "cookie": f"sessionid={INSTA_SESSION_ID};"}

LINK_TO_MESSAGE = {}
MESSAGE_TO_MESSAGE = defaultdict(list)
LINK_QUEUE = deque()
MESSAGE_QUEUE = deque()

QUEUE_SIZES = 5000


bot = hikari.GatewayBot(token=DISCORD_TOKEN)


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


def no_preview(message_text: str, link: str) -> bool:
    """
    Checks if the found url is inside the no-preview <brackets>.
    """
    return f"<{link}>" in message_text


def get_insta_data(insta_url: str) -> dict:
    """
    Scrape data about posted link from Instagram.
    """
    post = Post(insta_url)
    post.scrape(headers=HEADERS)
    data = {
        'thumbnail_url': post.display_url,
        'title': post.accessibility_caption,
        'author_name': post.full_name,
        'caption': post.caption,
        'likes': post.likes,
    }
    return data


def create_embed(link: str, insta_data: dict) -> hikari.embeds.Embed:
    """
    Prepare the embed object to be posted.
    """
    embed = hikari.embeds.Embed(
        title="Title",
        description=insta_data['caption'],
        url=link,
    )

    if insta_data['author_name'] != 'nan':
        embed.title = insta_data['author_name']
    elif insta_data['username'] != 'nan':
        embed.title = insta_data['username']
    else:
        embed.title = "Couldn't get username"

    embed.set_image(insta_data['thumbnail_url'])
    embed.add_field(name="Likes:", value=insta_data['likes'])

    embed.set_footer(text="Instagram embeds on Discord are broken, but I'll see what I can do.",
                     icon="https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png")
    return embed


async def process_message_link(message: hikari.GuildMessageCreateEvent, link: str):
    """
    Get info from Instagram and post a reply with the preview.
    """
    if no_preview(message.content, link):
        return

    await message.get_channel().trigger_typing()
    async with aiohttp.ClientSession() as session:
        insta_data = get_insta_data(link)
        if is_spoiler(message.content, link):
            async with session.get(insta_data['thumbnail_url']) as img:
                img = await img.read()
            with tempfile.NamedTemporaryFile(mode='rb+', prefix='SPOILER_', suffix='.jpg') as tmp_file:
                tmp_file.write(img)
                tmp_file.seek(0)
                discord_file = hikari.files.File(tmp_file.name)
                sent_message = await message.get_channel().send(
                    content=f'Visit <{link}> to see this image '
                            f'(and possibly more!) on authors Instagram page.\n\n'
                            f'{insta_data.caption}',
                    attachment=discord_file,
                    reply=message.message, mentions_reply=False)
        else:
            sent_message = await message.get_channel().send(embed=create_embed(link, insta_data),
                                                            reply=message.message, mentions_reply=False)

    LINK_TO_MESSAGE[link] = sent_message
    MESSAGE_TO_MESSAGE[message.message_id].append(sent_message)
    LINK_QUEUE.appendleft(link)


@bot.listen()
async def create_message(event: hikari.GuildMessageCreateEvent) -> None:
    # We check there is actually content first, if no message content exists,
    # we would get `None' here.
    if event.is_bot or not event.content:
        return

    if event.embeds:
        return

    for link in INSTAGRAM_RE.findall(event.content):
        await process_message_link(event, link)
        MESSAGE_QUEUE.appendleft(event.message_id)


@bot.listen()
async def edit_message(event: hikari.GuildMessageUpdateEvent) -> None:
    if not event.old_message.content:
        return
    if not event.message.content:
        return
    before_links = INSTAGRAM_RE.findall(event.old_message.content)
    after_links = INSTAGRAM_RE.findall(event.message.content)

    # Removed links
    for removed_link in set(before_links).difference(after_links):
        await LINK_TO_MESSAGE[removed_link].delete()
        del LINK_TO_MESSAGE[removed_link]

    # Added links
    for new_link in set(after_links).difference(before_links):
        await process_message_link(event, new_link)

    # Got embeds
    if event.embeds:
        for msg in MESSAGE_TO_MESSAGE[event.message_id]:
            await msg.delete()
        del MESSAGE_TO_MESSAGE[event.message_id]


@bot.listen()
async def delete_message(event: hikari.GuildMessageDeleteEvent) -> None:
    try:
        for msg in MESSAGE_TO_MESSAGE[event.message_id]:
            await msg.delete()
    except KeyError:
        pass
    else:
        del MESSAGE_TO_MESSAGE[event.message_id]
        if event.message_id in MESSAGE_QUEUE:
            MESSAGE_QUEUE.remove(event.message_id)

bot.run()
