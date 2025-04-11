"""
Setup command for configuring the tool
"""

import click
from autosubnuclei.config.config_manager import ConfigManager

@click.command()
@click.option('--discord-webhook', prompt='Do you want to set up Discord notifications? (y/n)', 
              help='Set up Discord webhook for notifications')
def setup(discord_webhook: str) -> None:
    """
    Setup command for configuring AutoSubNuclei
    """
    config_manager = ConfigManager()

    if discord_webhook.lower() == 'y':
        webhook_url = click.prompt('Enter your Discord webhook URL')
        config_manager.set_discord_webhook(webhook_url)
        click.echo('Discord notifications enabled!')
    else:
        config_manager.disable_notifications()
        click.echo('Discord notifications disabled.')

    click.echo('Setup complete!') 