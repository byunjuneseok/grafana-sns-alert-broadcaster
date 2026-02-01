from dependency_injector import containers, providers

from channels import AWSConnectChannel, SlackChannel, TelegramChannel
from router import Router


class Container(containers.DeclarativeContainer):
    config = providers.Configuration(yaml_files=["./config.yaml"])

    telegram_channel = providers.Singleton(
        TelegramChannel,
        enabled=config.channels.telegram.enabled.as_(lambda x: str(x).lower() == "true"),
        bot_token=config.channels.telegram.bot_token,
        chat_id=config.channels.telegram.chat_id,
    )

    slack_channel = providers.Singleton(
        SlackChannel,
        enabled=config.channels.slack.enabled.as_(lambda x: str(x).lower() == "true"),
        webhook_url=config.channels.slack.webhook_url,
    )

    aws_connect_channel = providers.Singleton(
        AWSConnectChannel,
        enabled=config.channels.aws_connect.enabled.as_(lambda x: str(x).lower() == "true"),
        instance_id=config.channels.aws_connect.instance_id,
        contact_flow_id=config.channels.aws_connect.contact_flow_id,
        source_phone_number=config.channels.aws_connect.source_phone_number,
        destination_phone_number=config.channels.aws_connect.destination_phone_number,
    )

    router = providers.Singleton(
        Router,
        channels=providers.List(
            telegram_channel,
            slack_channel,
            aws_connect_channel,
        ),
        routing_config=config.routing,
        default_level=config.default_level,
    )
