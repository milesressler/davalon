import math

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import caches
from django.conf import settings
from slack import WebClient
from botcommands.models import Game, User, Character

SLACK_VERIFICATION_TOKEN = getattr(settings, 'SLACK_VERIFICATION_TOKEN', None)
SLACK_BOT_USER_TOKEN = getattr(settings, 'SLACK_BOT_USER_TOKEN', None)
Client = WebClient(SLACK_BOT_USER_TOKEN)


def character_options(game):
    return list(map(lambda char: {
            "text": {
                "type": "plain_text",
                "text": ('Add ' if char not in game.character_list else 'Remove ') + char.name,
                "emoji": True
            },
            "value": char.value.id
        }, [Character.Mordred, Character.Percival, Character.Oberon, Character.Morgana]))


def get_lobby_block_content(game):
    players = "\n".join(list(map(lambda x: x.username_link(), game.player_list)))
    if not players:
        players = "_no one has joined_"

    characters_map = game.get_characters()
    characters = "\n".join(list(map(lambda x: x.value.name, characters_map['good']))) \
                 + "\n" + str(characters_map['servants']) + " Loyal Servant(s) of Arthur\n\n" + \
                 "\n".join(list(map(lambda x: x.value.name, characters_map['bad'])))

    if characters_map['minions'] > 0:
        characters = characters + "\n" + str(characters_map['minions']) + " Minion(s) of Mordred"

    min_players = game.get_min_players()

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Game lobby is open!*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{len(game.player_list)} player(s) ready, {min_players} required to start"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*Players*\n"+players
                },
                {
                    "type": "mrkdwn",
                    "text": "*Characters*\n"+characters
                }
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "static_select",
                    "action_id": "toggle_character",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Add/remove characters",
                        "emoji": True
                    },
                    "options": character_options(game)
                }
            ]
        },
        {
            "type": "divider"
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Join Lobby",
                        "emoji": True
                    },
                    "action_id": "join_game_lobby",
                    "value": "join_game_lobby"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Exit Lobby",
                        "emoji": True
                    },
                    "action_id": "exit_game_lobby",
                    "value": "exit_game_lobby"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Start Game",
                        "emoji": True
                    },
                    "action_id": "start_game",
                    "value": "start_game"
                }
            ]
        }
    ]


class BotCommands(APIView):
    command = None

    def post(self, request, *args, **kwargs):
        data = request.data

        if self.command == 'start':
            self.handle_start(data)

        return Response(status=status.HTTP_200_OK)

    def handle_start(self, data):
        # Must be channel/group

        # text = event_message.get('text')  #
        channel = data.get('channel_id')
        user = data.get('user_name')
        user_id = data.get('user_id')
        message = 'DAvalot lobby is open!'
        forced = False
        if 'text' in data:
            forced = data['text'].lower() == 'force'

        current_game = caches['default'].get(channel)
        if current_game and not forced:
            # Client.chat_postMessage(channel=channel, text="Use `/davalot force` to cancel existing session")
            return True

        # check for existing game

        # create new game
        game = Game()
        game.channel_id = channel
        game.player_list = [User({'username': user, 'id': user_id})]
        game.character_list = [Character.Merlin, Character.Assassin]

        # send start message
        block_content = get_lobby_block_content(game)
        response = Client.chat_postMessage(channel=channel, text=message, blocks=block_content)

        game.slack_message_ts = response.data['ts']
        caches['default'].set(channel, game)

        return True

