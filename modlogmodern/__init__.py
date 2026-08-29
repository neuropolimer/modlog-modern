from .modlogmodern import ModLogModern


async def setup(bot):
    await bot.add_cog(ModLogModern(bot))
