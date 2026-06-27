"""
Dreamina Auto Register - Services Module
"""
from app.services.clash_manager import clash_manager, ClashManager
from app.services.cloudflare_kv import cf_kv_client, CloudflareKVClient
from app.services.random_generator import (
    random_generator, 
    RandomGenerator,
    generate_email,
    generate_password,
    generate_birth_date
)
from app.services.browser_stealth import BrowserStealth
from app.services.human_behavior import HumanBehavior

__all__ = [
    # Clash
    "clash_manager",
    "ClashManager",
    # Cloudflare KV
    "cf_kv_client",
    "CloudflareKVClient",
    # Random Generator
    "random_generator",
    "RandomGenerator",
    "generate_email",
    "generate_password",
    "generate_birth_date",
    # Browser
    "BrowserStealth",
    "HumanBehavior",
]
