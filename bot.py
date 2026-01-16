import os
import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

Thread(target=run_web).start()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")

vc_owner = {}  # vc_id: owner_id
def has_active_vc(user_id: int):
    return user_id in vc_owner.values()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Secret VC Bot Ready")
# ---------- VC管理UI ----------

class RenameModal(discord.ui.Modal, title="VC名変更"):
    new_name = discord.ui.TextInput(label="新しいVC名", max_length=50)

    def __init__(self, vc):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        await self.vc.edit(name=self.new_name.value)
        await interaction.response.send_message("VC名を変更しました。", ephemeral=True)

class AllowUserSelect(discord.ui.View):
    def __init__(self, vc):
        super().__init__()
        self.vc = vc

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="参加許可するユーザーを選択")
    async def select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        for user in select.values:
            await self.vc.set_permissions(user, view_channel=True, connect=True)
        await interaction.response.send_message("参加許可しました。", ephemeral=True)

class DenyUserSelect(discord.ui.View):
    def __init__(self, vc):
        super().__init__()
        self.vc = vc

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="非表示にするユーザーを選択")
    async def select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        for user in select.values:
            await self.vc.set_permissions(user, view_channel=False, connect=False)
            if user.voice and user.voice.channel == self.vc:
                await user.move_to(None)
        await interaction.response.send_message("非表示にしました。", ephemeral=True)

class VCControlPanel(discord.ui.View):
    def __init__(self, vc):
        super().__init__(timeout=None)
        self.vc = vc

    def is_owner(self, user):
        return vc_owner.get(self.vc.id) == user.id

    @discord.ui.button(label="📞 招待", style=discord.ButtonStyle.green)
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction.user):
            return await interaction.response.send_message("作成者のみ操作できます。", ephemeral=True)
        await interaction.response.send_message("追加するユーザーを選択", view=AllowUserSelect(self.vc), ephemeral=True)

    @discord.ui.button(label="⛔ 非表示", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction.user):
            return await interaction.response.send_message("作成者のみ操作できます。", ephemeral=True)
        await interaction.response.send_message("非表示にするユーザーを選択", view=DenyUserSelect(self.vc), ephemeral=True)

    @discord.ui.button(label="👁 招待者一覧", style=discord.ButtonStyle.blurple)
    async def list_users(self, interaction: discord.Interaction, button: discord.ui.Button):
        invited = []

        for target, perms in self.vc.overwrites.items():
            if isinstance(target, discord.Member):
                if perms.connect is True:
                    invited.append(target.display_name)

        if invited:
            text = "招待済みメンバー:\n" + "\n".join(invited)
        else:
            text = "招待されているメンバーはいません"

        await interaction.response.send_message(text, ephemeral=True)
    @discord.ui.button(label="📛 VC名変更", style=discord.ButtonStyle.gray)
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction.user):
            return await interaction.response.send_message("作成者のみ操作できます。", ephemeral=True)
        await interaction.response.send_modal(RenameModal(self.vc))

    @discord.ui.button(label="🗑️ VC削除", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction.user):
            return await interaction.response.send_message("作成者のみ操作できます。", ephemeral=True)

    # 作成者のVC記録を削除（1人1VC制限解除）
        vc_owner.pop(self.vc.id, None)

    # VCを削除
        await self.vc.delete()




# ---------- 秘密VC作成パネル ----------

class CreateSecretVCView(discord.ui.View):
    @discord.ui.button(label="裏vcを作成", style=discord.ButtonStyle.green)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):

        # すでに作っているかチェック
        if has_active_vc(interaction.user.id):
            return await interaction.response.send_message(
                "すでにあなた専用の秘密VCが存在します。削除してから作り直してください。",
                ephemeral=True
            )

        guild = interaction.guild

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, connect=True)
        }

        CATEGORY_ID = 1388494041951240347
        category = guild.get_channel(CATEGORY_ID)

        vc = await guild.create_voice_channel(
            name=f"🔒{interaction.user.display_name}",
            overwrites=overwrites,
            category=category
        )

        vc_owner[vc.id] = interaction.user.id

        await vc.send(
            f"🔒 **秘密VC管理パネル**\n作成者: {interaction.user.mention}",
            view=VCControlPanel(vc)
        )

        await interaction.response.send_message(
            f"秘密VCを作成しました: {vc.mention}",
            ephemeral=True
        )


# ---------- コマンド ----------

from discord import app_commands, Permissions

from discord import app_commands, Permissions

@bot.tree.command(name="secret_panel", description="秘密VC作成パネルを設置")
async def secret_panel(interaction: discord.Interaction):
    # 管理者権限チェック
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "権限がありません。", ephemeral=True
        )

    await interaction.channel.send(
        "🎧 **秘密VC作成パネル**\nボタンで完全非公開VCを作成できます。",
        view=CreateSecretVCView()
    )
    await interaction.response.send_message("パネルを設置しました。", ephemeral=True)


bot.run(TOKEN)
