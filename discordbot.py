import asyncio, discord, json, os, random, re, signal
from discord.ext import commands
from datetime import datetime, time
import time as regular_time

# record all players to file
player_file = "players.json"
name_list = None

# track game state
index = 0

alarm_interval = 3600

game_active = False

# create bot with / commands
bot = commands.Bot(command_prefix="/", case_insensitive=True, intents=discord.Intents.all())

# initialize players file read
def init():

    global name_list
    global index
    index = 0

    # read from file
    if os.path.exists(player_file):
        # Open the file in read mode
        with open(player_file, "r") as f:
            # Read the JSON string from the file
            json_string = f.read()

        # Convert the JSON string to a list of strings
        name_list = json.loads(json_string)

    if name_list is None:
        name_list = []

    # shuffle game list (silent begin)
    global game_list
    game_list = name_list.copy()
    random.shuffle(game_list)
    print("Silent Ready")
    print(game_list)

# save players to file
async def save():
    print("Saving..")
    # Open the file in write mode
    with open(player_file, "w") as f:
        # Write the JSON string to the file      
        f.write(json.dumps(name_list))

# command hello
@bot.command(description="Display simple hello")
async def hello(ctx):
    await ctx.send("Hello, world!")

# command add player
@bot.command(description="Adds player to game")
async def add(ctx, names: str):

    print("add command:")
    print(names)

    for name in names.split(","):
        if(name != ''):
            if(name in name_list):
                await ctx.channel.send(f"{name} already exists")
            else:
                name_list.append(name.strip())
                game_list.append(name.strip())
    name_list.sort()

    await save()
    await print_game(ctx)

# command clear 
@bot.command()
async def clear(ctx):
    name_list.clear()
    game_list.clear()
    print(name_list)
    os.remove(player_file)
    await ctx.channel.send("All players deleted")

# command remove
@bot.command()
async def remove(ctx, name: str):
    global index
    found = False
    if name in name_list:
        found = True
        name_list.remove(name)
    if name in game_list:
        game_list.remove(name)

    if found:
        await save()
        await ctx.channel.send(f"Removed {name}")

        if(index != 0):
            if(index > len(game_list)):
                index = len(game_list)-1
            await print_game(ctx)

    else:
        await ctx.channel.send(f"{name} not found")

# command being
@bot.command(aliases=["go", "start", "random", "randomize"])
async def begin(ctx):
    global index 
    index = 0
    global game_active
    game_active = True

    global game_list 
    game_list = name_list.copy()
    random.shuffle(game_list)

    await(print_game(ctx))

# command next/skip
@bot.command(aliases=["skip"])
async def next(ctx):
    global game_active
    global index
    print(index)
    if(index != len(game_list)-1):
        index += 1
        await print_game(ctx)
    else:
        if(game_active):
            await end_game(ctx)
        else:
            await begin(ctx) 

# message alarm
async def message_alarm(ctx, signal):

    if can_message_during_daytime():
        if game_active:
            output = f"{game_list[index]} this is your alarm - it is your turn"  
            print(output)
            output += "\n\n"
            await ctx.channel.send(output)
            
            # reoccuring
            signal.alarm(alarm_interval)
        else:
            print("game inactive - ending alarm")
    else:
        print("Ignoring alarm, continuing...")

        if game_active:
            signal.alarm(alarm_interval)

# can message during daytime?
def can_message_during_daytime():
    start_time = time(hour=10, minute=0)  # Create a time object for 10:00 AM.
    end_time = time(hour=22, minute=0)  # Create a time object for 10:00 PM.

    current_time = datetime.now().time()  # Get the current time as a time object.

    return start_time < current_time < end_time

# command end
@bot.command()
async def end(ctx):
    await end_game(ctx)

# command print, status
@bot.command(name="print", aliases=["status", "who"])
async def print_game(ctx):

    global game_active

    if not game_active:
        output = "Game is not active. Start with /begin"
        print(output)
        await ctx.channel.send(output)
        return

    game_active = True

    SECONDS_PER_HOUR = 3600

    interval_text = format(alarm_interval/SECONDS_PER_HOUR, ".0f")
    alarm_text = f"setting alarm to {interval_text} hour."
    print(alarm_text)
    signal.signal(signal.SIGALRM, lambda signum, frame: 
        # await alarm(ctx)
        asyncio.create_task(message_alarm(ctx, signal))
    )
    signal.alarm(alarm_interval)

    global index

    if(len(game_list) == 0):
        await ctx.channel.send("Add players first with /add @\{name\} command")
        return
    
    # account for player removal mid-game
    if(index > len(game_list)-1):
        index = len(game_list)-1

    output = ""

    # new game
    if(index == 0):
        output = "New Game begin! - "
        output += f"{alarm_text}\n\n"

    # current turn
    output += f"{game_list[index]} it's your turn!\n\n"

    # all players
    i = 0
    for name in game_list:
        if i == index:
            output += "--> "
        else:
            output += "    "
        i += 1
        output += f"{name}\n"

    print(output)

    await ctx.channel.send(output)

# print only what exists in saved name list (not game list)
async def print_simple(ctx):
    await ctx.channel.send(str(name_list))

# end game without starting again
async def end_game(ctx):
    global index
    global game_active
    game_active = False
    index = len(game_list)-1
    print("Game inactive")
    await ctx.channel.send("Game over! Start new with /begin")

# bot on message to channel
@bot.event
async def on_message(message):
    
    if message.author == bot.user:
        return

    # Use a regular expression to remove any Discord ID from message.content.
    message_text = re.sub(r"<@\d+>\s*", "", message.content)
    
    print(f"{message.author.mention} sent {message_text}")

    # message inteded for bot
    if bot.user in message.mentions:
        print("Message intended for bot")

    # bot was mentioned
    if bot.user in message.mentions:
        # respond to hello
        if ("hello" in message_text or "hi" in message_text):
            # Construct the response message.
            response = f"Hello {message.author.mention}! How are you doing?"
            await message.channel.send(response)
        # not understood
        else:
            await message.channel.send(f"Pardon? {message.author.mention}. Try /help")
    else:
        await bot.process_commands(message)

    # if active player responding
    if(str(message.author.id) in game_list[index]):
        print("Active player is responding")

        containsImage = False

        # image detection
        if message.attachments:
            for attachment in message.attachments:
                # if attachment.is_image:
                if attachment.filename.endswith((".png", ".jpg", ".gif")):
                    print("Progressing game")
                    containsImage = True

                    # progress
                    if(index == len(game_list)-1):
                        await end_game(message)
                    else:
                        await next(message)
        # do not progress
        if not containsImage:
            print("Active player is chatting")


# Open the file in read-only mode.
with open("bot_token.txt", "r") as f:

    init()

    # Read the contents of the file.
    bot_token = f.read().strip()

    # bot.run(bot_token)
    bot.run(bot_token)