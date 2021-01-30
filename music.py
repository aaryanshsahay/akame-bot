import discord
from discord.ext import commands

import asyncio
import youtube_dl

#See if a link is a URL
import validators

#mat
from math import ceil
import random

from fetchYoutube import *

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
                        
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
            
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot, token):
        self.bot = bot
        self.fetch = FetchYoutube(token)
        self.queue = []
        self.loop = False
        self.player = None
    
    @commands.command(pass_context=True, aliases=['Skip'])
    async def skip(self, ctx):
        """Skip the current track"""

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        await ctx.send(f'**`{ctx.author}`**: Skipped the song!')

        if self.loop:
            last_played = self.queue[0]
            del self.queue[0]
            self.queue.append(last_played)
        else:
            del self.queue[0]


    @commands.command(pass_context=True)
    async def pause(self, ctx):
        """Pause the current song"""
        try:
            ctx.voice_client.pause()
            await ctx.send(":white_check_mark: Pause!")
        except:
            await ctx.send(":x: Turtle isn't singing!")


    #Resume music
    @commands.command(pass_context=True)
    async def resume(self, ctx):
        """Resume the current song"""
        try:
            ctx.voice_client.resume()
            await ctx.send(":white_check_mark: Música retomada!")
        except:
            await ctx.send(":x: Turtle hasn't started singing yet!")


    #Show the queue
    @commands.command(pass_context=True, aliases=['q'])
    async def queue(self, ctx, page=1):
        """Show the current songs in queue.
        !queue [page]"""
        string = '```Playing Right Now: {}\n\n'.format(self.fetch.parse_name(self.queue[0]))
        start_in = 1 + 15*(page-1)
        go_to = 16 + 15*(page-1)
        if page > ceil(len(self.queue)/15):
            await ctx.send("Not too many songs in the queue! Wait! You can add more, and then you can acess page {}".format(page))
        else:
            while start_in < go_to and start_in < len(self.queue):
                if start_in < 10:
                    number = str(start_in)+ ' '
                else:
                    number = start_in
                string += '{} ->\t{} \n'.format(number, self.fetch.parse_name(self.queue[start_in]))
                start_in += 1
            string += '\nPage {}\{}```'.format(page, (ceil(len(self.queue)/15)))
            await ctx.send(string)


    #Enable and disable the queue loop
    @commands.command(pass_context=True, aliases=['qloop'])
    async def loop(self, ctx):
        """Enable/Disable Queue Loop"""

        self.loop = not self.loop
        if self.loop:
            await ctx.send(":white_check_mark: Loop ativado!")
        else:
            await ctx.send(":x: Loop desativado!")


    @commands.command(pass_context=True, aliases=['clean','cleanq'])
    async def clear(self, ctx):
        """Clean Queue"""
        self.queue = []
        await ctx.send(":white_check_mark: Bye, songs! :cry:")

    @commands.command()
    async def play(self, ctx, *args):
        """Plays from a url or a search query (almost anything youtube_dl supports)"""

        content = ""
        for i in args:
            content += i + " "
        content = content.split()

        if content:
            pseudo_url = content[0]

            # Radio
            if validators.url(pseudo_url) and ("youtube" in pseudo_url) and ("radio" in pseudo_url):
                await ctx.send(":x: I can't play Youtube Radio playlists!")

            # Playlist
            elif validators.url(pseudo_url) and ("youtube" in pseudo_url) and ("list" in pseudo_url):
                self.queue = self.fetch.parse_playlist(pseudo_url)
                
                await ctx.send(":white_check_mark: Adicionou a playlist!")

            # Youtube Video
            elif validators.url(pseudo_url) and ("youtube" in pseudo_url) and ("watch" in pseudo_url):
                self.queue += [content[0],]

                await ctx.send(":white_check_mark: **{}** adicionou a música **{}**!".format("Turtle", url_data.title.string[:-10]))

            # Random URL
            elif validators.url(pseudo_url):
                await ctx.send(":x: This is not a music video!")

            # Query Search
            else:
                video = ytdl.extract_info(f"ytsearch:{content}", download=False)['entries'][0]
                self.queue.append(video['webpage_url'])

                await ctx.send(":white_check_mark: {} added the song **{}**!".format("Turtle", video['title']))

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send("Changed volume to {}%".format(volume))

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        self.queue = []
        await ctx.voice_client.disconnect()

    @play.after_invoke
    @skip.after_invoke
    async def ensure_play(self, ctx):
        if not ctx.voice_client.is_playing():
            while self.queue:
                async with ctx.typing():
                    self.player = await YTDLSource.from_url(self.queue[0], loop=self.bot.loop, stream=True)
                    ctx.voice_client.play(self.player, after=lambda e: print('Player error: %s' % e) if e else None)
                
                embedVar = discord.Embed(title="Start Playing", description='Now playing: {}'.format(self.player.title), color=0x0099ff)
                await ctx.send(embed=embedVar)

                duration = self.player.duration + 5
                await asyncio.sleep(duration)

                if self.loop:
                    last_played = self.queue[0]
                    del self.queue[0]
                    self.queue.append(last_played)
                else:
                    del self.queue[0]

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")