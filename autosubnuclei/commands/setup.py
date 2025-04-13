"""
Setup command for configuring the tool
"""

import click
import os
import logging
from getpass import getpass
from pathlib import Path

from autosubnuclei.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

def validate_webhook(webhook: str) -> bool:
    """
    Validate if a webhook URL looks legitimate
    """
    return webhook.startswith("http") and len(webhook) > 10

def validate_telegram_token(token: str) -> bool:
    """
    Validate if a Telegram bot token looks legitimate
    """
    return ":" in token and len(token) > 10

def validate_telegram_chat_id(chat_id: str) -> bool:
    """
    Validate if a Telegram chat ID looks legitimate
    """
    # Chat IDs can be negative for groups
    if chat_id.startswith('-'):
        chat_id = chat_id[1:]
    return chat_id.isdigit() or chat_id.startswith('@')

@click.command()
@click.option('--discord', is_flag=True, help='Configure Discord notifications')
@click.option('--slack', is_flag=True, help='Configure Slack notifications')
@click.option('--telegram', is_flag=True, help='Configure Telegram notifications')
@click.option('--disable', is_flag=True, help='Disable all notifications')
def setup(discord: bool, slack: bool, telegram: bool, disable: bool):
    """Setup configuration for the tool"""
    config_manager = ConfigManager()
    
    # If no specific option is provided, show menu
    if not any([discord, slack, telegram, disable]):
        show_setup_menu(config_manager)
        return
        
    # Handle each option
    if disable:
        config_manager.disable_notifications()
        click.echo("✅ Notifications disabled successfully")
        return
        
    if discord:
        setup_discord(config_manager)
    
    if slack:
        setup_slack(config_manager)
        
    if telegram:
        setup_telegram(config_manager)

def show_setup_menu(config_manager: ConfigManager) -> None:
    """Show interactive setup menu"""
    click.echo("📋 AutoSubNuclei Setup")
    click.echo("=" * 40)
    click.echo("Select an option:")
    click.echo("1. Configure Discord notifications")
    click.echo("2. Configure Slack notifications")
    click.echo("3. Configure Telegram notifications")
    click.echo("4. Disable all notifications")
    click.echo("0. Exit setup")
    
    choice = click.prompt("Enter your choice", type=int, default=0)
    
    if choice == 0:
        click.echo("Exiting setup...")
        return
    elif choice == 1:
        setup_discord(config_manager)
    elif choice == 2:
        setup_slack(config_manager)
    elif choice == 3:
        setup_telegram(config_manager)
    elif choice == 4:
        config_manager.disable_notifications()
        click.echo("✅ Notifications disabled successfully")
    else:
        click.echo("❌ Invalid choice")
        show_setup_menu(config_manager)

def setup_discord(config_manager: ConfigManager) -> None:
    """Set up Discord webhook"""
    click.echo("\n🔧 Discord Webhook Setup")
    click.echo("=" * 40)
    click.echo("Enter your Discord webhook URL.")
    click.echo("You can create a webhook in your Discord server settings > Integrations > Webhooks")
    
    webhook = click.prompt("Discord Webhook URL", type=str, default="")
    
    if webhook and validate_webhook(webhook):
        config_manager.set_discord_webhook(webhook)
        click.echo("✅ Discord webhook configured successfully")
    else:
        click.echo("❌ Invalid webhook URL. Notifications will be disabled.")
        
def setup_slack(config_manager: ConfigManager) -> None:
    """Set up Slack webhook"""
    click.echo("\n🔧 Slack Webhook Setup")
    click.echo("=" * 40)
    click.echo("Enter your Slack webhook URL.")
    click.echo("You can create a webhook in your Slack workspace settings > Apps > Incoming Webhooks")
    
    webhook = click.prompt("Slack Webhook URL", type=str, default="")
    
    if webhook and validate_webhook(webhook):
        config_manager.set_slack_webhook(webhook)
        click.echo("✅ Slack webhook configured successfully")
    else:
        click.echo("❌ Invalid webhook URL. Slack notifications will be disabled.")
        
def setup_telegram(config_manager: ConfigManager) -> None:
    """Set up Telegram bot"""
    click.echo("\n🔧 Telegram Bot Setup")
    click.echo("=" * 40)
    click.echo("To set up Telegram notifications, you need:")
    click.echo("1. A Telegram bot token (create one using @BotFather)")
    click.echo("2. Your chat ID (talk to @userinfobot to get yours)")
    
    token = click.prompt("Telegram Bot Token", type=str, default="")
    chat_id = click.prompt("Telegram Chat ID", type=str, default="")
    
    if token and chat_id and validate_telegram_token(token) and validate_telegram_chat_id(chat_id):
        config_manager.set_telegram_bot(token, chat_id)
        click.echo("✅ Telegram bot configured successfully")
    else:
        click.echo("❌ Invalid Telegram bot token or chat ID. Telegram notifications will be disabled.") 