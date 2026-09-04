from __future__ import annotations

import logging
import re
from copy import copy
from typing import Optional, Tuple

import discord
from redbot.core import Config, commands, modlog
from redbot.core.bot import Red

log = logging.getLogger("red.neuropolimer.modlogmodern")

_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


async def _modern_case_message_content(case, embed: bool = True):
    """Render Red ModLog cases with cleaned warning metadata everywhere.

    Stored case data is never changed. For warning cases we temporarily hide
    Red Warnings' trailing unwarn instruction while rendering, then expose the
    warning ID as its own field/line.
    """
    original = getattr(modlog.Case, "_modlogmodern_original_message_content", None)
    if original is None:
        original = modlog.Case.message_content

    if getattr(case, "action_type", None) != "warning":
        return await original(case, embed)

    clean_reason, warning_id = ModLogModern._clean_warning_reason(case)
    if not warning_id or clean_reason == getattr(case, "reason", None):
        return await original(case, embed)

    # Render a shallow copy instead of mutating the shared Case object.
    # Other ModLog listeners may receive the same instance concurrently.
    rendered_case = copy(case)
    rendered_case.reason = clean_reason
    rendered = await original(rendered_case, embed)

    if embed:
        rendered.insert_field_at(
            0,
            name="ID предупреждения",
            value=warning_id,
            inline=False,
        )
        return rendered

    return f"{rendered}\n**ID предупреждения:** {warning_id}"


class ModLogModern(commands.Cog):
    """A drop-in renderer for Red's core ModLog cases."""

    __author__ = "neuropolimer"
    __version__ = "0.3.1"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=82920261652001, force_registration=True)
        self.config.register_guild(
            channel_id=None,
            enabled=True,
            messages={},
            takeover_active=False,
            previous_core_channel_id=None,
            previous_warnings_toggle=None,
        )


    async def cog_load(self) -> None:
        # Patch the shared Case renderer so case/casesfor/listcases/history use
        # the same cleaned warning output as the live ModLogModern channel.
        if not hasattr(modlog.Case, "_modlogmodern_original_message_content"):
            setattr(
                modlog.Case,
                "_modlogmodern_original_message_content",
                modlog.Case.message_content,
            )
        modlog.Case.message_content = _modern_case_message_content

    def cog_unload(self) -> None:
        original = getattr(modlog.Case, "_modlogmodern_original_message_content", None)
        if original is not None and modlog.Case.message_content is _modern_case_message_content:
            modlog.Case.message_content = original
            delattr(modlog.Case, "_modlogmodern_original_message_content")

    @staticmethod
    def _case_user_id(case) -> Optional[int]:
        user = getattr(case, "user", None)
        if isinstance(user, int):
            return user
        return getattr(user, "id", None)

    @classmethod
    def _clean_warning_reason(cls, case) -> Tuple[Optional[str], Optional[str]]:
        """Strip Red Warnings' trailing unwarn hint and return its warning ID.

        Red's Warnings cog stores the warning under ctx.message.id and then appends
        a localized sentence containing an inline-code unwarn command to the
        ModLog reason. We intentionally key off the command's numeric arguments
        rather than its translated text, so this also works with non-English bots.
        """
        reason = getattr(case, "reason", None)
        if not reason:
            return reason, None

        clean_reason, separator, hint = reason.rpartition("\n\n")
        if not separator:
            return reason, None

        code_blocks = _INLINE_CODE_RE.findall(hint)
        if not code_blocks:
            return reason, None

        command = code_blocks[-1].strip().split()
        if len(command) < 3:
            return reason, None

        warned_user_id = str(cls._case_user_id(case) or "")
        candidate_user_id = command[-2]
        warning_id = command[-1]

        if not candidate_user_id.isdigit() or not warning_id.isdigit():
            return reason, None
        if warned_user_id and candidate_user_id != warned_user_id:
            return reason, None

        return clean_reason.rstrip(), warning_id

    async def _render_case(self, case, use_embed: bool):
        """Use the globally patched Red Case renderer."""
        return await case.message_content(use_embed)

    async def _configured_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = await self.config.guild(guild).channel_id()
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _effective_takeover(self, guild: discord.Guild) -> bool:
        """Detect both current and pre-0.3.0 takeover state."""
        settings = await self.config.guild(guild).all()
        if settings["takeover_active"]:
            return True
        if not settings["enabled"] or not settings["channel_id"]:
            return False
        try:
            core_channel = await modlog.get_modlog_channel(guild)
        except RuntimeError:
            core_channel = None
        return core_channel is None

    async def _send_case(self, case) -> None:
        guild = case.guild
        settings = await self.config.guild(guild).all()
        if not settings["enabled"] or not settings["channel_id"]:
            return

        channel = guild.get_channel(settings["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            use_embed = await self.bot.embed_requested(channel)
            case_content = await self._render_case(case, use_embed)
            if use_embed:
                message = await channel.send(embed=case_content)
            else:
                message = await channel.send(case_content)
        except discord.Forbidden:
            log.info(
                "ModLogModern cannot send case #%s in guild %s: missing permissions.",
                case.case_number,
                guild.id,
            )
            return
        except discord.HTTPException:
            log.exception(
                "ModLogModern failed to send case #%s in guild %s.",
                case.case_number,
                guild.id,
            )
            return

        async with self.config.guild(guild).messages() as messages:
            messages[str(case.case_number)] = message.id

    @commands.Cog.listener()
    async def on_modlog_case_create(self, case) -> None:
        await self._send_case(case)

    @commands.Cog.listener()
    async def on_modlog_case_edit(self, case) -> None:
        guild = case.guild
        settings = await self.config.guild(guild).all()
        if not settings["enabled"] or not settings["channel_id"]:
            return

        message_id = settings["messages"].get(str(case.case_number))
        if not message_id:
            return

        channel = guild.get_channel(settings["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            use_embed = await self.bot.embed_requested(channel)
            case_content = await self._render_case(case, use_embed)
            message = channel.get_partial_message(int(message_id))
            if use_embed:
                await message.edit(content=None, embed=case_content)
            else:
                await message.edit(content=case_content, embed=None)
        except discord.NotFound:
            async with self.config.guild(guild).messages() as messages:
                messages.pop(str(case.case_number), None)
        except discord.Forbidden:
            log.info(
                "ModLogModern cannot edit case #%s in guild %s: missing permissions.",
                case.case_number,
                guild.id,
            )
        except discord.HTTPException:
            log.exception(
                "ModLogModern failed to edit case #%s in guild %s.",
                case.case_number,
                guild.id,
            )

    @commands.group(name="modlogmodern", aliases=["mlmodern"], invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def modlogmodern(self, ctx: commands.Context) -> None:
        """Configure the modern ModLog output."""
        await self._send_status(ctx)

    @modlogmodern.command(name="channel")
    async def modlogmodern_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Set the channel used by ModLogModern."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f"ModLogModern будет писать в {channel.mention}.")

    @modlogmodern.command(name="takeover")
    async def modlogmodern_takeover(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Use ModLogModern as the only visible Red ModLog output."""
        if channel is None:
            if not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("Укажи текстовый канал для логов.")
                return
            channel = ctx.channel

        guild_config = self.config.guild(ctx.guild)
        settings = await guild_config.all()

        # Save the state only on the first takeover. Re-running takeover to move
        # the modern channel must not overwrite the original Red/Warn settings.
        effective_takeover = await self._effective_takeover(ctx.guild)
        if not settings["takeover_active"]:
            try:
                previous_core_channel = await modlog.get_modlog_channel(ctx.guild)
            except RuntimeError:
                previous_core_channel = None

            # Pre-0.3.0 installations did not persist takeover state. If core
            # ModLog is already disabled while modern output is enabled, the
            # best safe migration target is the current modern log channel.
            previous_core_id = (
                previous_core_channel.id
                if previous_core_channel is not None
                else settings["channel_id"] if effective_takeover else None
            )
            await guild_config.previous_core_channel_id.set(previous_core_id)

        await guild_config.channel_id.set(channel.id)
        await guild_config.enabled.set(True)

        # Keep Red's core case engine and case database alive, but stop its native
        # message output. create_case() still stores the case and dispatches
        # on_modlog_case_create, which this cog consumes.
        await modlog.set_modlog_channel(ctx.guild, None)

        # This is the separate Warnings-cog channel notification seen as the
        # first duplicate message. Disable it when taking over the log output.
        warnings_cog = self.bot.get_cog("Warnings")
        warnings_notice_disabled = False
        if warnings_cog is not None and hasattr(warnings_cog, "config"):
            try:
                warnings_config = warnings_cog.config.guild(ctx.guild)
                if not effective_takeover:
                    previous_toggle = await warnings_config.toggle_channel()
                    await guild_config.previous_warnings_toggle.set(previous_toggle)
                await warnings_config.toggle_channel.set(False)
            except Exception:
                log.exception("Failed to disable Warnings channel notification.")
            else:
                warnings_notice_disabled = True

        await guild_config.takeover_active.set(True)

        extra = (
            " Отдельное сообщение Warnings также отключено."
            if warnings_notice_disabled
            else ""
        )
        await ctx.send(
            f"ModLogModern активирован в {channel.mention}. "
            "Стандартный вывод Red ModLog отключён, база case'ов сохранена."
            + extra
        )

    @modlogmodern.command(name="on")
    async def modlogmodern_on(self, ctx: commands.Context) -> None:
        """Enable ModLogModern output."""
        channel = await self._configured_channel(ctx.guild)
        if channel is None:
            await ctx.send("Сначала задай канал: `[p]modlogmodern channel #канал`.")
            return
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f"ModLogModern включён: {channel.mention}.")

    @modlogmodern.command(name="off")
    async def modlogmodern_off(self, ctx: commands.Context) -> None:
        """Disable ModLogModern output without changing Red core ModLog."""
        if await self._effective_takeover(ctx.guild):
            await ctx.send(
                "Сейчас активен takeover: стандартный Red ModLog отключён. "
                "Чтобы не оставить сервер вообще без видимых логов, используй "
                "`modlogmodern release` вместо `off`."
            )
            return
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("ModLogModern отключён.")

    @modlogmodern.command(name="release")
    async def modlogmodern_release(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Return visible logging to Red and restore the pre-takeover Warnings state."""
        guild_config = self.config.guild(ctx.guild)
        settings = await guild_config.all()
        effective_takeover = await self._effective_takeover(ctx.guild)

        if channel is None:
            if effective_takeover:
                previous_id = settings["previous_core_channel_id"]
                previous_channel = ctx.guild.get_channel(previous_id) if previous_id else None
                modern_channel = ctx.guild.get_channel(settings["channel_id"])
                channel = (
                    previous_channel
                    if isinstance(previous_channel, discord.TextChannel)
                    else modern_channel
                    if isinstance(modern_channel, discord.TextChannel)
                    else None
                )
            else:
                if not isinstance(ctx.channel, discord.TextChannel):
                    await ctx.send("Укажи текстовый канал для стандартного ModLog.")
                    return
                channel = ctx.channel

        await modlog.set_modlog_channel(ctx.guild, channel)

        warnings_restored = False
        previous_toggle = settings["previous_warnings_toggle"]
        warnings_cog = self.bot.get_cog("Warnings")
        if (
            effective_takeover
            and previous_toggle is not None
            and warnings_cog is not None
            and hasattr(warnings_cog, "config")
        ):
            try:
                await warnings_cog.config.guild(ctx.guild).toggle_channel.set(previous_toggle)
            except Exception:
                log.exception("Failed to restore Warnings channel notification setting.")
            else:
                warnings_restored = True

        await guild_config.enabled.set(False)
        await guild_config.takeover_active.set(False)
        await guild_config.previous_core_channel_id.set(None)
        await guild_config.previous_warnings_toggle.set(None)

        core_text = channel.mention if channel is not None else "отключён"
        extra = " Настройка Warnings восстановлена." if warnings_restored else ""
        await ctx.send(
            f"Стандартный Red ModLog: {core_text}; ModLogModern отключён." + extra
        )

    @modlogmodern.command(name="status")
    async def modlogmodern_status(self, ctx: commands.Context) -> None:
        """Show current ModLogModern and Red ModLog output state."""
        await self._send_status(ctx)

    async def _send_status(self, ctx: commands.Context) -> None:
        settings = await self.config.guild(ctx.guild).all()
        modern_channel = ctx.guild.get_channel(settings["channel_id"])

        try:
            core_channel = await modlog.get_modlog_channel(ctx.guild)
        except RuntimeError:
            core_channel = None

        modern_value = (
            modern_channel.mention
            if isinstance(modern_channel, discord.TextChannel)
            else "не задан"
        )
        core_value = core_channel.mention if core_channel else "отключён"

        effective_takeover = await self._effective_takeover(ctx.guild)
        legacy_suffix = (
            " (мигрированное старое состояние)"
            if effective_takeover and not settings["takeover_active"]
            else ""
        )

        await ctx.send(
            "\n".join(
                (
                    f"ModLogModern: {'включён' if settings['enabled'] else 'выключен'}",
                    f"Takeover: {'активен' if effective_takeover else 'нет'}{legacy_suffix}",
                    f"Канал ModLogModern: {modern_value}",
                    f"Стандартный Red ModLog: {core_value}",
                )
            )
        )
