from pathlib import Path

import discord, os
from discord.ext import commands

class BotSetup(commands.Bot) :
    def __init__(self) :
        self._cogs = [p.stem for p in Path(".").glob("./bot/cogs/*.py")]
        super().__init__(
            command_prefix = self.prefix, 
            case_insensitive = True,
            intents = discord.Intents.all(),
            )

    def setup(self) :
        print("Setting Up ...")
        
        for cog in self._cogs :
            self.load_extension(f"bot.cogs.{cog}")
            print(f" Loaded '{cog}' cog.")
        
        print("Setup Complete!")
    
    def run(self) :
        self.setup()
        
        with open("bot/data/token.0", "r", encoding="utf-8") as tk :
            TOKEN = tk.read()
        
        print("Loading bot ... ")
        super().run(TOKEN, reconnect=True)
    
    async def shutdown(self) :
        print("Shutting down server to discord ...")
        await super().close()
    
    async def close(self) :
        print("Closing on keyboard interrupt ...")
        await self.shutdown()
    
    async def on_connect(self) :
        print(f" Connected to discord! (latency : {self.latency*1000:,.0f} ms)")
    
    async def on_resumed(self) :
        print("Bot resumed!")
    
    async def on_disconnect(self) :
        print("Bot disconnected!")
    
    async def on_ready(self) :
        self.client_id = (await self.application_info()).id    
        await self.change_presence(activity=discord.Game("and simping"), status = discord.Status.idle)
        print("Bot is ready :)")
    
    async def prefix(self, bot, msg) :
        return commands.when_mentioned_or(".")(bot, msg)
    
    async def process_command(self, msg) :
        ctx = await self.get_context(msg, cls=commands.Context)
        
        if ctx.command is not None :
            await self.invoke(ctx)
    
    async def on_message(self, msg) :
        if not msg.author.bot :
            await self.process_commands(msg)


# async def on_error(self, err, *args, **kwargs) :
#    raise

# async def on_command_error(self, ctx, exc) :
#    raise getattr(exc, "original", exc)


# bk-bot-mkb(bot settings), Created by BK Project
# Based on Carberra