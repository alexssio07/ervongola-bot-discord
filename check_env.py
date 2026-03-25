import os
import dotenv
from dotenv import load_dotenv

pre_token = os.getenv("DISCORD_TOKEN")
pre_token_display = f"{pre_token[:10]}...{pre_token[-7:]}" if pre_token else "None"
print(f"Token prima di load_dotenv: {pre_token_display}")

load_dotenv(override=True)
post_token = os.getenv("DISCORD_TOKEN")
post_token_display = f"{post_token[:10]}...{post_token[-7:]}" if post_token else "None"
print(f"Token dopo load_dotenv(override=True): {post_token_display}")
