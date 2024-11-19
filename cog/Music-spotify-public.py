# MIT
import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import asyncio
from typing import Dict, List
from discord.ui import Modal, TextInput, View, Select

# Spotify API 資訊
SPOTIPY_CLIENT_ID = ''
SPOTIPY_CLIENT_SECRET = ''
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET))

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.start_nodes())
        self.players: Dict[int, wavelink.Player] = {}
        self.volume = {}
        self.repeat_mode = {} 
        self.channel_info = {}  
        self.node: wavelink.Node = None  # 用於儲存節點對象

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id:
            guild_id = member.guild.id
            
            # 確保 self.channel_info 是字典
            if isinstance(self.channel_info, dict):
                # 確保 self.channel_info[guild_id] 是列表
                channels = self.channel_info.get(guild_id, [])
                if not isinstance(channels, list):
                    channels = [channels]  # 將非列表轉換為列表
                
                # 檢查 before.channel 是否存在於 self.channel_info
                if before.channel and before.channel.id in channels:
                    # 刪除 channel_info 中的 guild_id 鍵
                    self.channel_info.pop(guild_id, None)


    async def get_vloume(self, guild_id):
        try:
            volume = self.volume.get(guild_id)
        except Exception as e:
            volume=30
        return volume

    async def get_recommendations(self, track_id: str) -> str:
    # 獲取推薦歌曲
        recommendations = sp.recommendations(seed_tracks=[track_id], limit=1)
        
        # 確保有推薦歌曲返回
        if not recommendations['tracks']:
            return ""
        
        # 獲取推薦歌曲的名稱和藝術家名稱
        track = recommendations['tracks'][0]
        query = f"{track['name']} {track['artists'][0]['name']}"
        
        # 使用 YouTube 名稱和藝術家名稱進行 Spotify 搜索
        results = sp.search(q=query, type='track', limit=1)
        
        # 確保有返回的搜索結果
        if not results['tracks']['items']:
            return ""
        
        # 獲取匹配的 Spotify URL
        spotify_track = results['tracks']['items'][0]
        spotify_url = spotify_track['external_urls']['spotify']
        
        # 返回 Spotify URL
        return spotify_url
   

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                nodes = [wavelink.Node(uri="https://lavalink.top", password="password")]
                await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)
                self.node = nodes[0]  # 儲存節點對象
                print("Lavalink 節點已成功連接")
                break
            except Exception as e:
                print(f"連接節點失敗: {e}")
                await asyncio.sleep(10)  # 等待10秒後重試

    async def check_node(self, interaction: discord.Interaction) -> bool:
        if not self.node:
            await interaction.response.send_message("未連接到節點。", ephemeral=True)
            return False
        return True

    async def search_spotify_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        if not current:
            return []
        results = sp.search(q=current, type='track', limit=7)
        tracks = results['tracks']['items']
        return [app_commands.Choice(name=f"{track['name']} - {track['artists'][0]['name']}", value=track['external_urls']['spotify']) for track in tracks]
    
    async def get_player(self, guild: discord.Guild) -> wavelink.Player:
        player: wavelink.Player = guild.voice_client
        if not player:
            if guild.voice_client:
                player: wavelink.player
                if not player:
                    player = await guild.voice_client.move_to(guild.voice_client.channel)
                    self.players[guild.id] = player
            else:
                return None
        return player
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player: wavelink.Player = payload.player
        
        if not player:
            return
        
        guild_id = player.guild.id
        volume = await self.get_vloume(guild_id)
        chaneel_id = self.channel_info.get(guild_id)
        channel = self.bot.get_channel(chaneel_id)
        # 檢查是否啟用重複播放
        if self.repeat_mode.get(guild_id, False):
            track: wavelink.Playable = payload.track
            await player.play(track, volume=30)
    
            if channel:
                custom_emoji = self.bot.get_emoji(1259199046825021480)
                embed = discord.Embed(
                    title=f"{str(custom_emoji)} 操作成功",
                    description=f"重新播放: **`{track.title}`** by `{track.author}`",
                    color=discord.Color.blue()
                )
                await channel.send(embed=embed)
        else:
            # 播放下一首歌曲
            if not player.queue.is_empty:
                next_track = player.queue.get()
                await player.play(next_track, volume=volume)
    
                if channel:
                    custom_emoji = self.bot.get_emoji(1259199046825021480)
                    embed = discord.Embed(
                        title=f"{str(custom_emoji)} 操作成功",
                        description=f"開始播放: **`{next_track.title}`** by `{next_track.author}`",
                        color=discord.Color.blue()
                    )
                    await channel.send(embed=embed)
            else:
                # 如果隊列為空，獲取推薦歌曲
                recommended_tracks = await self.get_recommendations(payload.track.uri)
    
                if recommended_tracks:
                    tracks = await wavelink.Playable.search(recommended_tracks)
                    player.queue.put(tracks)  # 這裡不需要 await
    
                    if not player.queue.is_empty:
                        next_track = player.queue.get()
                        await player.play(next_track, volume=volume)
    
                        if channel:
                            custom_emoji = self.bot.get_emoji(1259199046825021480)
                            embed = discord.Embed(
                                title=f"{str(custom_emoji)} 操作成功",
                                description=f"開始播放推薦: **`{next_track.title}`** by `{next_track.author}`",
                                color=discord.Color.blue()
                            )
                            await channel.send(embed=embed)
                    else:
                        if channel:
                            await channel.send("隊列已經結束，沒有更多歌曲可以播放，且無法獲取推薦。")
                else:
                    if channel:
                        await channel.send("隊列已經結束，沒有更多歌曲可以播放，且無法獲取推薦。")
                    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        print(f"Node {payload.node!r} is ready !")
    
    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player) -> None:
        if not player:
            return
        guild_id = player.guild.id
        chaneel_id = self.channel_info.get(guild_id)
        channel = self.bot.get_channel(chaneel_id)
        await channel.send(f"The player has been inactive for `{player.inactive_timeout}` seconds. Goodbye!")
        await player.disconnect()
        
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player: wavelink.Player = payload.player
        guild_id = player.guild.id
        if not player:
            return
        
        chaneel_id = self.channel_info.get(guild_id)
        channel = self.bot.get_channel(chaneel_id)

        original: wavelink.Playable = payload.original
        track: wavelink.Playable = payload.track
    
        embed: discord.Embed = discord.Embed(title="現在播放：")
        embed.description = f"**{track.title}** by `{track.author}`"
    
        if track.artwork:
            embed.set_image(url=track.artwork)
    
        if original and original.recommended:
            embed.description += f"\n\n`該曲目是透過推薦的 {track.source}`"
    
        if track.album.name:
            embed.add_field(name="專輯", value=track.album.name)
    
        # 發送消息到點歌的頻道
        if channel:
            await channel.send(embed=embed)
    

    @app_commands.command(name="音樂-播放音樂", description="播放音樂(Spotify)")
    @app_commands.autocomplete(query=search_spotify_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str):
        if not await self.check_node(interaction):
            return

        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("您需要先加入一個語音頻道。", ephemeral=True)
            return

        player: wavelink.Player = interaction.guild.voice_client
        
        if not player:
            channel = interaction.channel
            vic_channel = interaction.user.voice.channel
            player = await vic_channel.connect(cls=wavelink.Player)
            self.players[interaction.guild.id] = player
            self.channel_info[interaction.guild.id] = channel.id
        
        player.autoplay = wavelink.AutoPlayMode.disabled
        try:
            if "spotify.com" in query:
                result = sp.track(query)
                track_url = result['external_urls']['spotify']
                tracks = await wavelink.Playable.search(track_url)
            else:
                tracks = await wavelink.Playable.search(query)

            if not tracks:
                await interaction.followup.send("找不到這首歌。")
                return

            if isinstance(tracks, wavelink.Playlist):
                added = len(tracks.tracks)
                for track in tracks.tracks:
                    await player.queue.put_wait(track)
                custom_emoji = self.bot.get_emoji(1259199046825021480)
                embed = discord.Embed(
                    title=f"{str(custom_emoji)} 操作成功",
                    description=f"已將播放清單 **`{tracks.name}`** ({added} 首歌曲) 添加到隊列中。",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
            else:
                track = tracks[0]
                await player.queue.put_wait(track)
                custom_emoji = self.bot.get_emoji(1259199046825021480)
                embed = discord.Embed(
                    title=f"{str(custom_emoji)} 操作成功",
                    description=f"已將 **`{track.title}`** 添加到隊列中。",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)

            if not player.playing:
                await player.play(player.queue.get(), volume=30)

                # 發送消息到點歌的頻道
                if interaction.channel:
                    custom_emoji = self.bot.get_emoji(1259199046825021480)
                    embed = discord.Embed(
                        title=f"{str(custom_emoji)} 操作成功",
                        description=f"開始播放: **`{track.title}`** by `{track.author}`",
                        color=discord.Color.blue()
                    )
                    await interaction.channel.send(embed=embed)

        except wavelink.exceptions.LavalinkLoadException as e:
            await interaction.followup.send(f"加載音樂時發生錯誤: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"發生未知錯誤: {str(e)}", ephemeral=True)

    @app_commands.command(name="音樂-移除列隊歌曲編號", description="移除隊列中的指定歌曲")
    @app_commands.describe(index="要移除的歌曲編號 (從 1 開始)")
    async def remove_track(self, interaction: discord.Interaction, index: int):
        if not await self.check_node(interaction):
            return

        player: wavelink.Player = interaction.guild.voice_client

        if not player or not player.connected:
            await interaction.response.send_message("機器人不在語音頻道中。", ephemeral=True)
            return

        if index < 1 or index > len(player.queue):
            await interaction.response.send_message(
                f"無效的歌曲編號。請選擇 1 到 {len(player.queue)} 之間的編號。", ephemeral=True
            )
            return

        removed_track = player.queue.delete(index)  # 從隊列中移除指定歌曲
        custom_emoji = self.bot.get_emoji(1259199046825021480)
        embed = discord.Embed(
            title=f"{str(custom_emoji)} 操作成功",
            description=f"已移除: **`{removed_track.title}`** by `{removed_track.author}`",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )
    
    @app_commands.command(name="音樂-清除列隊歌曲", description="清除隊列中的所有歌曲")
    async def clear_queue(self, interaction: discord.Interaction):
        if not await self.check_node(interaction):
            return


        player: wavelink.Player = interaction.guild.voice_client

        if not player:
            await interaction.response.send_message("機器人不在語音頻道中。", ephemeral=True)
            return

        player.queue.clear()
        custom_emoji = self.bot.get_emoji(1259199046825021480)
        embed = discord.Embed(
            title=f"{str(custom_emoji)} 操作成功",
            description="隊列已清除。",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="音樂-調整音量", description="調整音量")
    async def volume(self, interaction: discord.Interaction, volume: int):
        if not await self.check_node(interaction):
            return

        player = await self.get_player(interaction.guild)
        if player is None:
            await interaction.response.send_message("無法取得播放器，請稍後再試。", ephemeral=True)
            return

        if 0 <= volume <= 100:
            await player.set_volume(volume)
            self.volume[interaction.guild.id] = volume
            custom_emoji = self.bot.get_emoji(1259199046825021480)
            embed = discord.Embed(
                title=f"{str(custom_emoji)} 操作成功",
                description=f"音量已設置為 {volume}%",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("音量必須在0到100之間。", ephemeral=True)


    @app_commands.command(name="音樂-調整音樂順序", description="調整音樂播放順序")
    @app_commands.describe(from_index="要移動的歌曲編號 (從 1 開始)", to_index="新位置的編號 (從 1 開始)")
    async def move_track(self, interaction: discord.Interaction, from_index: int, to_index: int):
        player: wavelink.Player = interaction.guild.voice_client

        if not player:
            await interaction.response.send_message("機器人不在語音頻道中。", ephemeral=True)
            return

        queue_length = len(player.queue)

        if from_index < 1 or from_index > queue_length:
            await interaction.response.send_message(
                f"無效的歌曲編號。請選擇 1 到 {queue_length} 之間的編號作為原位置。", ephemeral=True
            )
            return

        if to_index < 1 or to_index > queue_length:
            await interaction.response.send_message(
                f"無效的歌曲編號。請選擇 1 到 {queue_length} 之間的編號作為新位置。", ephemeral=True
            )
            return

        try:
            f_index = int(from_index)
        except wavelink.exceptions.Indexerror as e:
            await interaction.followup.send(f"數量錯誤: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"發生錯誤: {str(e)}", ephemeral=True)
        
        try:
            t_index = int(to_index)
        except Exception as e:
            await interaction.followup.send(f"發生錯誤: {str(e)}", ephemeral=True)
        track = player.queue.get_at(f_index)  # 從原位置移除
        player.queue.pop_at(t_index, track)
        custom_emoji = self.bot.get_emoji(1259199046825021480)
        embed = discord.Embed(
            title=f"{str(custom_emoji)} 操作成功",
            description=f"已將歌曲 **`{track.title}`** 從位置 {from_index} 移動到位置 {to_index}。",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )


    @app_commands.command(name="音樂-列隊查看", description="查看當前的播放列隊")
    async def queue(self, interaction: discord.Interaction):
        if not await self.check_node(interaction):
            return

        player = await self.get_player(interaction.guild)
        if not player or not player.playing:
            return await interaction.response.send_message("我目前沒有在播放任何音樂。")
        
        queue = player.queue
        
        if not queue:
            return await interaction.response.send_message("隊列目前是空的。")
        
        queue_list = "\n".join([f'{i + 1}. {track.title}' for i, track in enumerate(queue)])
        custom_emoji = self.bot.get_emoji(1259199046825021480)
        embed = discord.Embed(
            title=f"{str(custom_emoji)} 操作成功",
            description=f'當前隊列:\n{queue_list}',
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="音樂-查看節點連線", description="檢查是否連接到節點")
    async def check_node_cmd(self, interaction: discord.Interaction):
        if self.node:
            custom_emoji = self.bot.get_emoji(1259199046825021480)
            await interaction.response.send_message(f"{str(custom_emoji)} 已連接到節點。")
        else:
            await interaction.response.send_message("未連接到任何節點。")

    @app_commands.command(name="音樂-跳過歌曲", description="跳過當前歌曲")
    async def skip(self, interaction: discord.Interaction):
        if not await self.check_node(interaction):
            return

        player = await self.get_player(interaction.guild)
        custom_emoji = self.bot.get_emoji(1259199046825021480)
        if player:
            await player.stop()
            embed = discord.Embed(
                title=f"{str(custom_emoji)} 操作成功",
                description="以跳過歌曲",
                color=discord.Color.blue()
            )
            await interaction.response.send_message("已跳過當前歌曲。")
        else:
            await interaction.response.send_message("無法取得播放器，請稍後再試。", ephemeral=True)

    @app_commands.command(name="音樂-重複模式開關", description="切換重複播放模式")
    async def repeat(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            return
        
        guild_id = interaction.guild.id
        self.repeat_mode[guild_id] = not self.repeat_mode.get(guild_id, False)

        mode = "啟用" if self.repeat_mode[guild_id] else "禁用"
        custom_emoji = self.bot.get_emoji(1259199046825021480)
        embed = discord.Embed(
            title=f"{str(custom_emoji)} 操作成功",
            description=f"重複播放模式已{mode}。",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="音樂-離開頻道", description="離開頻道")
    async def leave(self, interaction: discord.Interaction):
        if not await self.check_node(interaction):
            return
        custom_emoji = self.bot.get_emoji(1259199046825021480)

        
        
        player: wavelink.Player = interaction.guild.voice_client

        if not player or not player.connected:
            await interaction.response.send_message("機器人不在語音頻道中。", ephemeral=True)
            return

        if player:
            await player.disconnect()
            await interaction.response.send_message('已成功斷開連接。')
        els
