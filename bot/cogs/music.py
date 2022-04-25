import discord, wavelink
from discord.ext import commands

import random, asyncio, re
import datetime as dt
import typing as t

from enum import Enum

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
}

# Commands Error Check Exception
class AlreadyConnectedToChannel(commands.CommandError) :
    pass

class NoVoiceChannel(commands.CommandError) :
    pass

class QueueIsEmpty(commands.CommandError) :
    pass

class NoTracksFound(commands.CommandError) :
    pass

class PlayerIsAlreadyPause(commands.CommandError) :
    pass

class NoMoreTracks(commands.CommandError) :
    pass

class NoPreviousTracks(commands.CommandError) :
    pass

class InvalidRepeatMode(commands.CommandError) :
    pass

class VolumeTooHigh(commands.CommandError) :
    pass

class VolumeTooLow(commands.CommandError) :
    pass

class MaxVolume(commands.CommandError) :
    pass

class MinVolume(commands.CommandError) :
    pass

class NotConnected(commands.CommandError) :
    pass

class NoTracksInQueue(commands.CommandError) :
    pass

class RepeatMode(Enum) :
    NONE = 0
    ONE = 1
    ALL = 2
    

# Main Classes and Objects
class Queue :
    def __init__(self) :
        self._queue = []
        self.position = 0
        self.repeat_mode = RepeatMode.NONE
        
    @property
    def is_empty(self) :
        return not self._queue

#    @property
#    def first_track(self) :
#        if not self._queue :
#            raise QueueIsEmpty
#        
#        return self._queue[0]

    @property
    def current_track(self) :
        if not self._queue :
            raise QueueIsEmpty
        
        if self.position <= len(self._queue) - 1 :
            return self._queue[self.position]
    
    @property
    def upcoming(self) :
        if not self._queue :
            raise QueueIsEmpty
        
        return self._queue[self.position + 1:]
    
    @property
    def history(self) :
        if not self._queue :
            raise QueueIsEmpty
        
        return self._queue[:self.position]

    @property
    def length(self) :
        return len(self._queue)

    def add(self, *args) :
        self._queue.extend(args)
    
    def get_next_track(self) :
        if not self._queue :
            raise QueueIsEmpty
        
        self.position += 1
        
        if self.position < 0 :
            return None
        elif self.position > len(self._queue) - 1 :
            if self.repeat_mode == RepeatMode.ALL :
                self.position = 0
            else :
                return None
        
        return self._queue[self.position]
    
    def shuffle(self) :
        if not self._queue :
            raise QueueIsEmpty
        
        upcoming = self.upcoming
        random.shuffle(upcoming)
        self._queue = self._queue[:self.position + 1]
        self._queue.extend(upcoming)
    
    def set_repeat_mode(self, mode) :
        if mode == "none" :
            self.repeat_mode = RepeatMode.NONE
        elif mode == "1" :
            self.repeat_mode = RepeatMode.ONE
        elif mode == "all" :
            self.repeat_mode = RepeatMode.ALL
    
    def empty(self) :
        self._queue.clear()
        self.position = 0
    

## Main Object
class Player(wavelink.Player) :
    def __init__(self, *args, **kwargs) :
        super().__init__(*args, **kwargs)
        self.queue = Queue()
    
    async def connect(self, ctx, channel=None) :
        if self.is_connected :
            raise AlreadyConnectedToChannel

        if (channel := getattr(ctx.author.voice, "channel", channel)) is None :
            raise NoVoiceChannel
        
        await super().connect(channel.id)
        return channel
            
    async def teardown(self) :
        try :
            await self.destroy()
        except KeyError :
            pass
    
    async def add_tracks(self, ctx, tracks) :
        if not tracks :
            raise NoTracksFound
        
        if isinstance(tracks, wavelink.TrackPlaylist) :
            self.queue.add(*tracks.tracks)
        elif len(tracks) == 1 :
            self.queue.add(tracks[0])
            embed = discord.Embed(
                title = "Information",
                description = f"Added `{tracks[0].title}` to queue!",
                colour = ctx.author.colour.blue()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        else :
            if (track := await self.choose_track(ctx, tracks)) is not None:
                self.queue.add(track)
                embed = discord.Embed(
                    title = "Information",
                    description = f"Added `{track.title}` to the queue!",
                    colour = ctx.author.colour.blue()
                )
                embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
                await ctx.send(embed=embed)
        
        if not self.is_playing and not self.queue.is_empty :
            await self.start_playback()
    
    async def choose_track(self, ctx, tracks) :
        def _check(r, u) :
            return (
                r.emoji in OPTIONS.keys()
                and u == ctx.author
                and r.message.id == msg.id
            )
        
        embed = discord.Embed(
            title = "Choose the song",
            description = (
                "\n".join(
                    f"**{i+1}.** {t.title} ({t.length//60000}:{str(t.length%60).zfill(2)})"
                    for i,t in enumerate(tracks[:5])
                )
            ),
            colour = ctx.author.colour,
            timestamp = dt.datetime.utcnow()
        )
        embed.set_author(name="Query results")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        
        msg = await ctx.send(embed=embed)
        for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))] :
            await msg.add_reaction(emoji)
        
        try :
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=_check)
        except asyncio.TimeoutError :
            await msg.delete()
            await ctx.message.delete()
        else :
            await msg.delete()
            return tracks[OPTIONS[reaction.emoji]]
    
    async def start_playback(self) :
        await self.play(self.queue.current_track)
    
    async def advance(self) :
        try :
            if (track := self.queue.get_next_track()) is not None :
                await self.play(track)
        except QueueIsEmpty :
            pass
    
    async def repeat_track(self) :
        await self.play(self.queue.current_track)

class Music(commands.Cog, wavelink.WavelinkMixin) :
    def __init__(self, bot) :
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())
        self.bot.remove_command("help")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after) :
        if not member.bot and after.channel is None :
            if not [m for m in before.channel.members if not m.bot] :
                await self.get_player(member.guild).teardown()
    
    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node) :
        print(f"Wavelink node '{node.identifier}' ready!")
    
    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self, node, payload) :
        if payload.player.queue.repeat_mode == RepeatMode.ONE :
            await payload.player.repeat_track()
        else :
            await payload.player.advance()
    
    async def cog_check(self, ctx) :
        if isinstance(ctx.channel, discord.DMChannel) :
            await ctx.send("Something went wrong, try again later!")
            return False
        
        return True
    
    # Setting up nodes
    async def start_nodes(self) :
        await self.bot.wait_until_ready()
        
        nodes = {
           "MAIN" : {
               "host": "127.0.0.1",
               "port": 2333,
               "rest_uri": "http://127.0.0.1:2333",
               "password": "bkserverlink",
               "identifier": "MAIN",
               "region": "singapore",
           } 
        }
        # This node is from lavalink.jar(with application.yml)
        # you can find it in jdk inside bin folder
        
        for node in nodes.values() : 
            await self.wavelink.initiate_node(**node)
    
    def get_player(self, obj) :
        if isinstance(obj, commands.Context) :
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild) :
            return self.wavelink.get_player(obj.id, cls=Player)
    
    @commands.command(name="connect", aliases=["join", "con"])
    async def connect_command(self, ctx, *, channel: t.Optional[discord.VoiceChannel]) :
        player = self.get_player(ctx)
        channel = await player.connect(ctx, channel)
        embed = discord.Embed(
            title = "Information",
            description = f"Connected to {channel.name}!",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @connect_command.error
    async def connect_command_error(self, ctx, exc) :
        if isinstance(exc, AlreadyConnectedToChannel) :
            embed = discord.Embed(
                title = "Information",
                description = "The bot is already connected in channel!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)

        elif isinstance(exc, NoVoiceChannel) :
            embed = discord.Embed(
                title = "Information",
                description = "No suitable voice channel was provided!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @commands.command(name="disconnect", aliases=["leave", "lv", "dc"])
    async def disconnect_command(self, ctx) :
        player = self.get_player(ctx)
        await player.teardown()
        embed = discord.Embed(
            title = "Information",
            description = "The bot is disconnected!!",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
    # in this code, disconnect is equal to teardown
    
    @commands.command(name="play", aliases=["p", "Assalamualaikum"])
    async def play_command(self, ctx, *, query: t.Optional[str]) :
        player = self.get_player(ctx)
        
        if not player.is_connected :
            await player.connect(ctx)
        
        if query is None :
            if player.queue.is_empty :
                raise QueueIsEmpty
            
            await player.set_pause(False)
            embed = discord.Embed(
                title = "Information",
                description = "Song Resumed!",
                colour = ctx.author.colour.blue()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        
        else :
            query = query.strip("<>")
            if not re.match(URL_REGEX, query) :
                query = f"ytsearch:{query}"
                
            await player.add_tracks(ctx, await self.wavelink.get_tracks(query))
    
    @play_command.error
    async def play_command_error(self, ctx, exc) :
        if isinstance(exc, QueueIsEmpty) :
            embed = discord.Embed(
                title = "Information",
                description = "No song in queue!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        
        elif isinstance(exc, NoVoiceChannel) :
            embed = discord.Embed(
                title = "Information",
                description = "No suitable voice channel was provided!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @commands.command(name="pause", aliases=["pa"])
    async def pause_command(self, ctx) :
        player = self.get_player(ctx)
        
        if player.is_paused :
            raise PlayerIsAlreadyPause
        
        await player.set_pause(True)
        embed = discord.Embed(
            title = "Information",
            description = "Song Paused!",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @pause_command.error
    async def pause_command_error(self, ctx, exc) :
        if isinstance(exc, PlayerIsAlreadyPause) :
            embed = discord.Embed(
                title = "Information",
                description = "The song already paused!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @commands.command(name="stop", aliases=["reset"])
    async def stop_command(self, ctx) :
        player = self.get_player(ctx)
        player.queue.empty()
        await player.stop()
        embed = discord.Embed(
            title = "Information",
            description = "Bot Stopped!",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @commands.command(name="skip", aliases=["s"])
    async def skip_command(self, ctx) :
        player = self.get_player(ctx)
        
        if not player.queue.upcoming :
            raise NoMoreTracks
        
        await player.stop()
        embed = discord.Embed(
            title = "Information",
            description = "Playing next song in queue!",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @skip_command.error
    async def queue_command_error(self, ctx, exc) :
        if isinstance(exc, QueueIsEmpty) :
            embed = discord.Embed(
                title = "Information",
                description = "Can't skip track while queue is empty!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        if isinstance(exc, NoMoreTracks) :
            embed = discord.Embed(
                title = "Information",
                description = "No more tracks in queue!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
#    @commands.command(name="back", aliases=["prev"])
#    async def back_command(self, ctx) :
#        player = self.get_player(ctx)
#        
#        if not player.queue.history :
#            raise NoPreviousTracks
#        
#        player.queue.position -= 2
#        await player.stop()
#        embed = discord.Embed(
#            title = "Information",
#            description = "Playing previous song in queue!",
#            colour = ctx.author.colour.blue()
#        )
#        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
#        await ctx.send(embed=embed)
#    
#    @back_command.error
#    async def queue_command_error(self, ctx, exc) :
#        if isinstance(exc, QueueIsEmpty) :
#            embed = discord.Embed(
#                title = "Information",
#                description = "Can't back track while queue is empty!!",
#                colour = ctx.author.colour.red()
#            )
#            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
#            await ctx.send(embed=embed)
#            
#        if isinstance(exc, NoPreviousTracks) :
#            embed = discord.Embed(
#                title = "Information",
#                description = "No song in back queue!!",
#                colour = ctx.author.colour.red()
#            )
#            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
#            await ctx.send(embed=embed)
    
#    @commands.command(name="shuffle", aliases=["sh"])
#    async def shuffle_command(self, ctx) :
#        player = self.get_player(ctx)
#        player.queue.shuffle()
#        embed = discord.Embed(
#            title = "Information",
#            description = "Queue Shuffled!",
#            colour = ctx.author.colour.blue()
#        )
#        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
#        await ctx.send(embed=embed)
#    
#    @shuffle_command.error
#       if isinstance(exc, QueueIsEmpty) :
#            embed = discord.Embed(
#                title = "Information",
#                description = "Can't shuffle playlist while queue is empty!!",
#                colour = ctx.author.colour.red()
#            )
#            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
#            await ctx.send(embed=embed)
            
    @commands.command(name="repeat")
    async def repeat_command(self, ctx, mode: str) :
        if mode not in ("none", "1", "all") :
            raise InvalidRepeatMode
        
        player = self.get_player(ctx)
        player.queue.set_repeat_mode(mode)
        embed = discord.Embed(
            title = "Information",
            description = f"The playlist set to repeat {mode}",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
        
    @commands.command(name="queue", aliases=["q"])
    async def queue_command(self, ctx, show: t.Optional[int] = 10) :
        player = self.get_player(ctx)
        
        if player.queue.is_empty :
            raise QueueIsEmpty
        
        embed = discord.Embed(
            title = "Queue List",
            description = 
                f"Showing up to next {show} tracks\n"
                f"Note! if the bot have bug, you can use 'stop' command and play again"
                ,
            colour = ctx.author.colour.blue(),
            timestamp = dt.datetime.utcnow()
        )
        embed.set_author(name="Query Results")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.add_field(
            name="Currently playing", 
            value=getattr(player.queue.current_track, "title", "No tracks currently playing."), 
            inline=False
        )
        if upcoming := player.queue.upcoming :
            embed.add_field(
                name="Next up",
                value="\n - ".join(t.title for t in upcoming[:show]),
                inline=False
            )
        
        msg = await ctx.send(embed=embed)

    @queue_command.error
    async def queue_command_error(self, ctx, exc) :
        if isinstance(exc, QueueIsEmpty) :
            embed = discord.Embed(
                title = "Information",
                description = "The Queue is empty!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @commands.group(name="volume", invoke_without_command=True)
    async def volume_group(self, ctx, volume: int) :
        player = self.get_player(ctx)
        
        if volume < 0 :
            raise VolumeTooLow
        
        if volume > 150 :
            raise VolumeTooHigh
        
        await player.set_volume(volume)
        embed = discord.Embed(
            title = "Information",
            description = f"Volume set to : {volume:,}%",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @volume_group.error
    async def volume_group_error(self, ctx, exc) :
        if isinstance(exc, VolumeTooLow) :
            embed = discord.Embed(
                title = "Information",
                description = "The volume is too low!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        elif isinstance(exc, VolumeTooHigh) :
            embed = discord.Embed(
                title = "Information",
                description = "The volume is too high!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @volume_group.command(name="up")
    async def volume_up_command(self, ctx) :
        player = self.get_player(ctx)
        
        if player.volume == 150 :
            raise MaxVolume
        
        await player.set_volume(value := min(player.volume + 10, 150))
        embed = discord.Embed(
            title = "Information",
            description = f"Volume set to {value:,}%",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
        
    @volume_up_command.error
    async def volume_up_command_error(self, ctx, exc) :
        if isinstance(exc, MaxVolume) :
            embed = discord.Embed(
                title = "Information",
                description = "The player is already at max volume!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @volume_group.command(name="down")
    async def volume_down_command(self, ctx) :
        player = self.get_player(ctx)
        
        if player.volume == 0 :
            raise MinVolume
        
        await player.set_volume(value := max(player.volume - 10, 0))
        embed = discord.Embed(
            title = "Information",
            description = f"Volume set to {value:,}%",
            colour = ctx.author.colour.red()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
        
    @volume_down_command.error
    async def volume_down_command_error(self, ctx, exc) :
        if isinstance(exc, MinVolume) :
            embed = discord.Embed(
                title = "Information",
                description = "The player is already at min volume!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @commands.command(name="playing", aliases=["np"])
    async def playing_command(self, ctx) :
        player = self.get_player(ctx)
        
        if not player.is_playing :
            raise PlayerIsAlreadyPause
        
        embed = discord.Embed(
            title = "Now Playing",
            colour = ctx.author.colour.blue(),
            timestamp = dt.datetime.utcnow()
        )
        embed.set_author(name="Playback Information")
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        embed.add_field(name = "Track title", value = player.queue.current_track.title, inline = False)
        embed.add_field(name = "Artist", value = player.queue.current_track.author, inline = False)
        
        position = divmod(player.position, 60000)
        length = divmod(player.queue.current_track.length, 60000)
        embed.add_field(
            name = "Position",
            value = f"{int(position[0])}:{round(position[1]/1000):02}/{int(length[0])}:{round(length[1]/1000):02}",
            inline = False
        )
        
        await ctx.send(embed=embed)

    @playing_command.error
    async def playing_command_error(self, ctx, exc) :
        if isinstance(exc, PlayerIsAlreadyPause) :
            embed = discord.Embed(
                title = "Information",
                description = "There is no song currently playing!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @commands.command(name="skipto", aliases=["goto"])
    async def skipto_command(self, ctx, index: int) :
        player = self.get_player(ctx)
        
        if player.queue.is_empty :
            raise QueueIsEmpty
        
        if not 0 <= index <= player.queue.length :
            raise NoMoreTracks
        
        player.queue.position = index - 2
        await player.stop()
        embed = discord.Embed(
            title = "Information",
            description = f"Playing song in {index}",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
        
    @skipto_command.error
    async def skipto_command_error(self, ctx, exc) :
        if isinstance(exc, QueueIsEmpty) :
            embed = discord.Embed(
                title = "Information",
                description = "No tracks in queue!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        elif isinstance(exc, NoMoreTracks) :
            embed = discord.Embed(
                title = "Information",
                description = "No index found in queue!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
    @commands.command(name="remove", aliases=["rem"])
    async def remove_command(self, ctx, index: int) :
        player = self.get_player(ctx)
        
        if not Player or not Player.is_connected :
            raise NotConnected
        
        if not 0 <= index <= player.queue.length :
            raise NoMoreTracks
        
        del player.queue._queue[index]
        embed = discord.Embed(
            title = "Information",
            description = f"Remove song for {index}",
            colour = ctx.author.colour.blue()
        )
        embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @remove_command.error
    async def remove_command_error(self, ctx, exc) :
        if isinstance(exc, NotConnected) :
            embed = discord.Embed(
                title = "Information",
                description = "The bot is not in voice channel!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
    
        if isinstance(exc, NoTracksInQueue) :
            embed = discord.Embed(
                title = "Information",
                description = "Couldn't find a track!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        
        if isinstance(exc, NoMoreTracks) :
            embed = discord.Embed(
                title = "Information",
                description = "No tracks are available on queue!!",
                colour = ctx.author.colour.red()
            )
            embed.set_footer(text = f"Requested by {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
            await ctx.send(embed=embed)
        
    @commands.command(name="help")
    async def help_command(self, ctx) :    
           
        desc = str(
            "`.play <url>` -> Play a song with url or title\n"
            "`.pause` -> Pause the song when you play it\n"
            "`.stop` -> Stop the song and delete all song from queue\n"
            "`.skip` -> Go to next song from queue\n"
            "`.rem` -> Remove the song with index track\n"
            "`.skipto <index>` -> Playing the next song from queue with index\n"
            "`.queue` -> See the queue list\n"
            "`.np` -> Displaying current track\n"
            "`.repeat <mode>` -> repeat the song when it play\n"
            "`.volume <index>` -> Setting up the volume\n"
            "`.leave` -> Disconnect the bot from voice channel\n"
        )
        
        embed = discord.Embed(
            title = "Music Commands",
            colour = ctx.author.colour.blue(),
            timestamp = dt.datetime.utcnow()
        )
        embed.set_author(name="Help Results")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.add_field(name="Commands", value = desc, inline = False)
        
        await ctx.send(embed=embed)
            

def setup(bot) :
    bot.add_cog(Music(bot))



# bk-bot-mkb(Music Cog), Created by BK Project
# using private server with lavalink
# Based on Carberra