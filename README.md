# Instagram Embeds bot

Hello! As you may have noticed, Discord sometimes has problems adding embed previews to messages containing links to 
Instagram posts. This bot aims to fix this, by providing previews of its own.

## Requirements

To run this bot, you'll need two things:

1. Obviously, you'll need a bot token for the bot to use. Put that token in the `DISCORD_TOKEN` environmental variable.
2. You'll also need an Instagram session id. This should be hidden somewhere in the Instagram cookies in your browser. 
   Once you find it, put it in the `INSTA_SESSION_ID` environmental variable.

## Running the bot

There are many ways to run this bot, but I'll describe two.

### Running the bot directly

1. If you don't have it, install [`pipenv`](https://pypi.org/project/pipenv/).
2. Run `pipenv sync` to download all dependencies.
3. Run the bot with `pipenv run python3 main.py`

### Using Docker to run the bot

You can also use docker to run the bot inside a container. Use this command to get it started:

`docker run -d -e DISCORD_TOKEN=<your_token> -e INSTA_SESSION_ID=<your_instagram_session> --name InstaBot palanaeum/instabot:latest`

## Disclaimer

This bot comes with no guarantee that it'll work or will be maintained. The way it's using Instagram session info is
not really compliant with what Instagram wants, so it's strongly advised not to use a session ID of your main Instagram
account as it may get banned. You have been warned, use it on your own risk.