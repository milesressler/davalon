import json
import requests
import random

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import caches
from django.conf import settings
from slack import WebClient
from slack.web.classes.interactions import MessageInteractiveEvent
from botcommands.views import get_lobby_block_content
from actions.board_management import get_game_board
from botcommands.models import Character, User, GameStage

SLACK_VERIFICATION_TOKEN = getattr(settings, 'SLACK_VERIFICATION_TOKEN', None)
SLACK_BOT_USER_TOKEN = getattr(settings, 'SLACK_BOT_USER_TOKEN', None)
Client = WebClient(SLACK_BOT_USER_TOKEN)


class Actions(APIView):
    def post(self, request, *args, **kwargs):
        try:
            json_data = json.loads(request.data['payload'])
            data = MessageInteractiveEvent(json_data)
            channel = data.channel.id
            game = caches['default'].get(channel)
            if not game:
                Client.chat_postMessage(channel=channel, text="Can't find game?!?!")

            else:
                game.player_list = game.player_list
                game.character_list = set(game.character_list)

                action_id = data.action_id
                username = (game.admin_user or data.user.name) if game.debug else data.user.name
                if action_id == 'join_game_lobby':
                    self.join_lobby(username, data.user.id, game)
                elif action_id == 'exit_game_lobby':
                    self.exit_lobby(username, game)
                elif action_id == 'start_game':
                    self.start_game(game)
                elif action_id == 'toggle_character':
                    self.toggle_character(data.value, game)
                elif action_id == 'toggle_quest_user':
                    self.toggle_quest_user(game, username, data.value)
                elif action_id == 'send_quest':
                    self.send_quest(game, username)
                elif action_id == 'approve_quest':
                    self.handle_vote(game, username, True)
                elif action_id == 'reject_quest':
                    self.handle_vote(game, username, False)
                elif action_id == 'succeed_quest':
                    self.handle_quest(game, username, True)
                elif action_id == 'fail_quest':
                    self.handle_quest(game, username, False)
                elif action_id == 'toggle_admin_act_as':
                    game.admin_user = data.value
                elif action_id == 'toggle_assassination_target':
                    self.handle_toggle_target(game, username, data.value)
                elif action_id == 'assassinate':
                    self.handle_assassinate(game, username)

                caches['default'].set(channel, game)

                if game.game_stage == GameStage.Lobby:
                    content = get_lobby_block_content(game)
                else:
                    content = get_game_board(game)

                push_new = action_id == 'push_down'
                if not push_new:
                    r = requests.post(url=data.response_url, json={'replace_original': True, 'blocks': content})
                else:
                    r = requests.post(url=data.response_url, json={'replace_original': False, 'blocks': []})
                    Client.chat_delete(channel=game.channel_id, ts=data.message_ts)
                    response = Client.chat_postMessage(channel=channel, blocks=content)
                    game.slack_message_ts = response.data['ts']
                    caches['default'].set(channel, game)
        except:
            print("exception caught")

        return Response(status=status.HTTP_200_OK)


    def exit_lobby(self, username, game):
        new_player_list = []
        for player in game.player_list:
            if player.username != username:
                new_player_list.append(player)
        game.player_list = new_player_list
        return True

    def join_lobby(self, username, userid, game):
        new_player_list = []
        for player in game.player_list:
            if player.username != username:
                new_player_list.append(player)
        new_player_list.append(User({'username': username, 'id': userid}))
        game.player_list = new_player_list
        return True

    def start_game(self, game):
        number_of_players = len(game.player_list)
        if number_of_players < game.get_min_players():
            if game.debug:
                additional = 0
                for i in range(game.get_min_players() - number_of_players):
                    additional = additional + 1
                    game.player_list.append(User({'username': 'milesressler' + str(i), 'id': 'U6YGRAH40'}))
                number_of_players = number_of_players + additional
            else:
                Client.chat_postMessage(channel=game.channel_id, text="Not enough players!")
                return False
        if number_of_players > 10:
            Client.chat_postMessage(channel=game.channel_id, text="Too many players!")
            return False

        # Set turns
        indexes = list(range(0, number_of_players))
        random.shuffle(indexes)
        game.player_turn_index = 0
        game.hammer_index = 4
        game.game_stage = GameStage.ChooseQuest

        possible_characters = game.get_characters()
        random.shuffle(possible_characters['all'])
        random.shuffle(game.player_list)
        for i in range(len(game.player_list)):
            game.player_list[i].turn_order = i
            game.player_list[i].character = possible_characters['all'][i]

        for player in game.player_list:
            self.send_user_message(game, player)

        game.message = "_Roles have been sent, check your DMs_"

        return True

    def send_user_message(self, game, player):
        userchannel = Client.im_open(user=player.id).data['channel']['id']
        player.channel = userchannel
        message_text = "Your character is: *" + player.character.name + "*\nTeam is *" + player.character.team + "*"
        if player.character == Character.Merlin:
            evil_usernames = []
            for player2 in game.player_list:
                if player2.character.evil and not player2 == Character.Mordred:
                    evil_usernames.append(player2.username_link())

            message_text = message_text + "\n_Evil Players:_ \n" + "\n".join(evil_usernames)

        if player.character.evil:
            evil_usernames = []
            for player2 in game.player_list:
                if player2.character.evil and not player2.character == Character.Oberon and not (player.username == player2.username):
                    evil_usernames.append(player2.username_link())
            message_text = message_text + "\n_Other Evil Players:_ \n" + "\n".join(evil_usernames)

        if player.character == Character.Percival:
            merlins = []
            for player2 in game.player_list:
                if player2.character in [Character.Merlin, Character.Morgana]:
                    merlins.append(player2.username_link())

            message_text = message_text + f"\n_Merlin is either_ {merlins[0]} _or_ {merlins[1]}"

        Client.chat_postMessage(channel=userchannel, text=message_text)


    def handle_toggle_target(self, game, username, selected_user):
        self.verify_user_turn(game, username)
        player = game.find_player_by_username(selected_user)
        game.assassination_target = player
        return True


    def toggle_user(self, username, game):
        is_present = False
        new_player_list = []
        for player in game.player_list:
            new_player_list.append(player)
            if player.username == username:
                is_present = True

        if not is_present:
            new_player_list.append({'username': username})

        game.player_list = new_player_list
        return True

    def toggle_character(self, character_id, game):
        character = Character.from_id(character_id)
        if character in game.character_list:
            if character == Character.Percival or character == Character.Morgana:
                game.character_list.remove(Character.Morgana)
                game.character_list.remove(Character.Percival)
            else:
                game.character_list.remove(character)
        else:
            if character == Character.Percival or character == Character.Morgana:
                game.character_list.add(Character.Morgana)
                game.character_list.add(Character.Percival)
            else:
                game.character_list.add(character)

        return True

    def send_quest(self, game, username):
        self.verify_user_turn(game, username)
        if len(game.proposed_quest['players']) == game.get_quester_count():
            game.game_stage = GameStage.VoteOnQuest
        return True

    def verify_user_turn(self, game, username):
        player = game.find_player_by_username(username)
        is_valid = False
        if game.game_stage == GameStage.ChooseQuest:
            is_valid = player.turn_order == game.player_turn_index
        elif game.game_stage == GameStage.VoteOnQuest:
            is_valid = True
        elif game.game_stage == GameStage.CompleteQuest:
            for quester in game.proposed_quest['players']:
                if quester.username == username:
                    is_valid = True

        if not is_valid and not game.debug:
            raise Exception("not your turn")

    def toggle_quest_user(self, game, username, selected_user):
        self.verify_user_turn(game, username)

        player = game.find_player_by_username(username)
        new_quester = game.find_player_by_username(selected_user)
        if player.turn_order == game.player_turn_index or True:
            current_quest = game.proposed_quest['players']
            exists = False
            updated_quest_list = []
            for i in current_quest:
                if i.username == selected_user:
                    exists = True
                else:
                    updated_quest_list.append(i)
            if not exists:
                updated_quest_list.append(new_quester)
            game.proposed_quest['players'] = updated_quest_list
        return True

    def handle_vote(self, game, username, vote):
        self.verify_user_turn(game, username)
        game.proposed_quest['votes'][username] = vote

        if len(game.proposed_quest['votes']) == len(game.player_list):
            vote_summary = f"for:"
            for player in game.proposed_quest['players']:
                vote_summary = vote_summary + " " + player.username_link()
            for k, v in game.proposed_quest['votes'].items():
                vote_summary = vote_summary + f"\n<@{k}> : *{'Approved' if v else 'Rejected'}*"
            if game.count_votes():
                # vote passed
                game.game_stage = GameStage.CompleteQuest
                game.message = f"Vote *passed* {vote_summary}"
                # Client.chat_postMessage(channel=game.channel_id, text=f"Vote *passed*\n{vote_summary}")
            else:
                game.message = f"Vote *did not pass*\n{vote_summary}"
                # Client.chat_postMessage(channel=game.channel_id, text=f"Vote *did not pass*\n{vote_summary}")
                game.reset_proposed_quest()
                if game.hammer_index != game.player_turn_index:
                    game.player_turn_index = game.player_turn_index + 1
                    if game.player_turn_index >= len(game.player_list):
                        game.player_turn_index = 0
                    game.game_stage = GameStage.ChooseQuest
                else:
                    game.game_stage = GameStage.Lost

        return True

    def handle_quest(self, game, username, quest_result):
        self.verify_user_turn(game, username)
        voter = game.find_player_by_username(username)
        game.quest_results[game.round][username] = voter.character.good or quest_result
        if len(game.quest_results[game.round]) == game.get_quester_count():
            quest_succeeded, succeeds, fails = game.count_quest(game.round)
            if quest_succeeded:
                game.message = "*Quest SUCCEEDED!*"
                # Client.chat_postMessage(channel=game.channel_id, text="*Quest SUCCEEDED!*")
            else:
                game.message = "*Quest FAILED!*"
                # Client.chat_postMessage(channel=game.channel_id, text="*Quest FAILED!*")

            game.next_round()

        return True

    def handle_assassinate(self, game, username):
        self.verify_user_turn(game, username)
        if not game.assassination_target:
            return True

        merlin_id = None
        for user in game.player_list:
            if user.character == Character.Merlin:
                merlin_id = user.id

        game.game_stage = GameStage.Lost if game.assassination_target.id == merlin_id else GameStage.Won
        return True

