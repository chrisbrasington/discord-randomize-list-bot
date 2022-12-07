#!/usr/bin/env python3
import asyncio, discord, json, os, random, re, signal
from discord.ext import commands
from datetime import datetime, time
import time as regular_time
from classes.gamestate import GameState, GameStateEncoder

# game state
state = None

# create bot with / commands
bot = commands.Bot(
    command_prefix="/", 
    case_insensitive=True, 
    intents=discord.Intents.all())

# initialize players file read
async def init():
    global bot, state
    state = GameState()

    if os.path.exists('gamestate.json'):
        with open('gamestate.json', 'r') as f:
            data = json.load(f)
            state = GameState(**data)
            print('Prior State Loaded from file')
    else:
        print('No prior state')

    if state.channel is None:
        print("Not is_listening on any channel")
    else:
        print(f"is_listening on {state.channel}")

    # shuffle game list (silent begin)
    # await state.Shuffle()
    # print("Silent Ready")

    print(await state.Serialize())

# command hello
@bot.command(brief="Hello, World")
async def hello(ctx):
    await ctx.send("Hello, world!")

def is_listening(ctx):
    global state
    return str(ctx.channel) == state.channel

# command listen - sets game channel
@bot.command(brief="Set listening to this channel")
async def listen(ctx):
    global state
    state.channel = str(ctx.channel)
    print(f"/listen {state.channel}")
    await ctx.channel.send(f"Now is_listening on {ctx.channel}")
    await state.Save()

# command add player
@bot.command(brief="Adds player to game. If game is active, goes to end of list")
async def add(ctx, names: str):
    global bot, state 
    if(not is_listening(ctx)):
        return

    if await state.Add(bot, names):
        await ctx.channel.send("Added Player")
        await state.DisplayConfig(ctx, bot)
    else:
        await ctx.channel.send(f"{name} already exists")

# command removes a player from the game
@bot.command(brief="Removes player from game")
async def remove(ctx, name: str):
    global state
    if(not is_listening(ctx)):
        return

    if await state.Remove(name):
        await ctx.channel.send(f"Removed {name}")
        await state.DisplayConfig(ctx, bot)
    else:
        await ctx.channel.send(f"{name} not found")

# command being
@bot.command(brief="Shuffles and starts new game",aliases=["go", "start", "random", "randomize"])
async def begin(ctx):
    global state
    await state.Begin(ctx, bot)

# command next/skip
@bot.command(brief="Progress to next player",aliases=["skip"])
async def next(ctx):
    if(not is_listening(ctx)):
        return
    global state
    await state.Next(ctx, bot)

# command end
@bot.command(brief="End game")
async def end(ctx):
    if(not is_listening(ctx)):
        return
    await end_game(ctx)

# set alarm
@bot.command(brief="Set player alarm in hours")
async def alarm(ctx, new_alarm: str):
    global state
    number = int(new_alarm)

    if number > 8:
        await ctx.channel.send("Yeah let's not go bigger than 8 hours. You can send 0 to disable")
        return

    if number == 0:
        await ctx.channel.send("Disabling alarm")
        state.alarm_hours = 0
    else:
        await ctx.channel.send(f"Setting alarm to {number} hour(s)")
        state.alarm_hours = number

        if state.active: 
            await ctx.channel.send(f"Congrats {ctx.author.mention}, you hit an edge case of changing the alarm mid-game. I will not start a new alarm until the next player in the game..")

# command print, status
@bot.command(brief="Prints current game status",name="print", aliases=["status", "who"])
async def print_game(ctx):
    global state
    await state.Display(ctx)
 
# end game without starting again
async def end_game(ctx):
    global state
    await state.End(ctx)

# command test
@bot.command(brief="Shows configuration of bot")
async def config(ctx):
    global state
    await state.DisplayConfig(ctx, bot)

# command test - sets players to test players
@bot.command(brief="aka /goblinmode - swaps players for test goblins",name="gametest", aliases=["testmode", "goblinmode"])
async def gametest(ctx):
    global state
    await state.TestMode(True, bot)
    await state.ReadAllUsers(bot)
    await state.DisplayConfig(ctx, bot)

# command restart - can unload test to real players
@bot.command(brief="Resets players (used for swapping out of test mode")
async def restart (ctx):
    global state
    await state.Restart(bot)

    await ctx.channel.send("Restarted")
    await state.DisplayConfig(ctx, bot)

@bot.command(brief="Toggles if @ messaging is used during turns")
async def silent(ctx):
    global state
    state.silent = not state.silent
    await ctx.channel.send(f"Silent: {state.silent}")
    await state.Save()

# bot on message to channel
@bot.event
async def on_message(ctx):
    global state

    if ctx.author == bot.user:
        return

    if(ctx.channel.type == discord.ChannelType.private):
        await ctx.channel.send(f"Why are you DM-ing me {ctx.author.mention}? ya weirdo.")
        await ctx.channel.send("Play games with me in your discord channel, check out the readme at https://github.com/chrisbrasington/discord-game-turn-bot")
        print(f"{ctx.author.mention} send a dm, replying and ignoring")
        return

    # might be missing due to game state loading
    if(state.mapping == {}):
        print('Reading all users first time')
        await ctx.channel.send('Reading usernames first time... one moment please...')
        await state.ReadAllUsers(bot)
    
    image_responding_channel = str(ctx.channel) == state.channel

    # Use a regular expression to remove any Discord ID from ctx.content.
    message_text = re.sub(r"<@\d+>\s*", "", ctx.content)
    
    # print(f"{ctx.author.mention} sent {message_text}")
    # print(image_responding_channel)
    # await print_simple(message)

    # message intended for bot
    if bot.user in ctx.mentions:
        print("Message intended for bot")

    # bot was mentioned
    if bot.user in ctx.mentions:
        # respond to hello
        if ("hello" in message_text or "hi" in message_text):
            # Construct the response ctx.
            response = f"Hello {ctx.author.mention}! How are you doing?"
            await ctx.channel.send(response)
        # not understood
        elif("right" in message_text):
            await ctx.channel.send("Fuck yeah {ctx.author.mention}")
        elif("why" in message_text or "what" in message_text):
            await ctx.channel.send("Sorry.. go ask chat.openai")
        elif("config" in message_text):
            await state.DisplayConfig(ctx, bot)
        else:
            await ctx.channel.send(f"{message_text}, you too {ctx.author.mention}.")

    # if active player responding
    if len(state.players) > 0:
        if(image_responding_channel and str(ctx.author.id) in state.players[state.index]):
            # print("Active player is responding")
            containsImage = False

            # image detection
            if ctx.attachments:
                for attachment in ctx.attachments:
                    # if attachment.is_image:
                    if attachment.filename.endswith((".png", ".jpg", ".gif")):
                        print("Progressing game")
                        containsImage = True

                        # progress
                        if(state.index == len(state.players)-1):
                            await state.End(ctx)
                            break
                        else:
                            await state.Next(ctx, bot)
                            break
            # do not progress
            if not containsImage:
                print("Active player is chatting")

    if ctx.content.startswith('/'):
        print(f"{ctx.author} sent {message_text}")
        await bot.process_commands(ctx)

# Open the file in read-only mode.
with open("bot_token.txt", "r") as f:

    asyncio.run(init())

    # Read the contents of the file.
    bot_token = f.read().strip()

    # bot.run(bot_token)
    bot.run(bot_token)

