import math
from enum import Enum
from collections import namedtuple


Char = namedtuple('Char', ['id', 'name', 'team'])


class Character(Enum):
    Merlin = Char('merlin', 'Merlin', 'Blue')
    Servant = Char('servant', 'Loyal Servant of Arthur', 'Blue')
    Percival = Char('percival', 'Percival', 'Blue')
    Assassin = Char('assassin', 'Assassin',  'Red')
    Morgana = Char('morgana', 'Morgana', 'Red')
    Oberon = Char('oberon', 'Oberon', 'Red')
    Mordred = Char('mordred', 'Mordred', 'Red')
    Minion = Char('minion', 'Minion of Mordred', 'Red')

    @staticmethod
    def from_id(id):
        for character in Character.all():
            if character.id == id:
                return character

    @property
    def name(self):
        return self.value.name

    @property
    def id(self):
        return self.value.id

    @property
    def team(self):
        return self.value.team

    @property
    def good(self):
        return self.value.team.lower() == 'blue'

    @property
    def evil(self):
        return not self.good

    @staticmethod
    def all():
        return [Character.Merlin,
                Character.Percival,
                Character.Servant,
                Character.Assassin,
                Character.Mordred,
                Character.Morgana,
                Character.Oberon,
                Character.Minion]


class GameStage(Enum):
    Lobby = 0
    ChooseQuest = 1
    VoteOnQuest = 2
    CompleteQuest = 3
    Assassinate = 4
    Lost = 5
    Won = 6


class User:
    username = None
    id = None
    channel = None
    character = None

    # default constructor
    def __init__(self, dictionary):
        for key in dictionary:
            setattr(self, key, dictionary[key])

    def username_link(self):
        return f"<@{self.username}>"


class Game:
    debug = True
    admin_user = None
    slack_message_ts = None

    channel_id = None
    game_stage = GameStage.Lobby

    player_turn_index = 0
    hammer_index = None
    round = 0

    player_list = []
    character_list = set()
    proposed_quest = {
        'players': [],
        'votes': dict()
    }

    quest_results = {0: dict(), 1: dict(), 2: dict(), 3: dict(), 4: dict()}
    assassination_target = None
    message = None

    def count_quest(self, round_num):
        results = self.quest_results[round_num]
        if not len(results) > 0:
            return None

        fails = sum(1 if not val else 0 for key, val in results.items())
        succeeds = sum(1 if val else 0 for key, val in results.items())

        if fails == 0:
            return True, succeeds, fails
        elif fails == 2:
            return False, succeeds, fails
        elif fails == 1:
            return (round_num == 3 and (len(self.player_list) > 6)), succeeds, fails

    def next_round(self):
        total_fails = 0
        total_passes = 0
        for i in range(0, (self.round + 1)):
            if len(self.quest_results[i]) > 0:
                result, succeed_count, fail_count = self.count_quest(i)
                if result:
                    total_passes = total_passes + 1
                else:
                    total_fails = total_fails + 1

        self.reset_proposed_quest()

        if total_passes >= 3:
            self.game_stage = GameStage.Assassinate
        elif total_fails >= 3:
            self.game_stage = GameStage.Lost
        else:
            self.game_stage = GameStage.ChooseQuest
            self.round = self.round + 1
            self.player_turn_index = self.player_turn_index + 1
            if self.player_turn_index >= len(self.player_list):
                self.player_turn_index = 0
            self.hammer_index = (self.player_turn_index + 4)
            if self.hammer_index >= len(self.player_list):
                self.hammer_index = self.hammer_index - len(self.player_list)

    def count_votes(self):
        votes_for = sum(1 if val else 0 for key, val in self.proposed_quest['votes'].items())
        votes_against = sum(1 if not val else 0 for key, val in self.proposed_quest['votes'].items())
        return votes_for > votes_against

    def find_player_by_username(self, username):
        for player in self.player_list:
            if player.username == username:
                return player

    def get_min_players(self):
        bad_count = sum(1 if char.evil else 0 for char in self.character_list)

        if bad_count == 4:
            return 10
        if bad_count == 3:
            return 7

        return 5

    def get_quester_count(self, round=None):
        number_of_players = len(self.player_list)
        rounds = {
            5: [2, 3, 2, 3, 3],
            6: [2, 3, 4, 3, 4],
            7: [2, 3, 3, 4, 4],
            8: [3, 4, 4, 5, 5],
            9: [3, 4, 4, 5, 5],
            10: [3, 4, 4, 5, 5]
        }
        return rounds[number_of_players][(round if round else self.round)]

    def reset_proposed_quest(self):
        self.proposed_quest = {
            'players': [],
            'votes': dict()
        }

    def get_player_quest_options(self):
        options = []
        for player in self.player_list:
            options.append({
                "text": {
                    "type": "plain_text",
                    "text": player.username
                },
                "value": player.username
            })
        return options

    def get_characters(self):
        min_players = self.get_min_players()
        total_characters = max(min_players, len(self.player_list))
        required_good_characters = math.ceil((total_characters + 1) / 2)
        required_bad_characters = math.floor((total_characters - 1) / 2)

        if total_characters == 9:
            required_good_characters = 6
            required_bad_characters = 3

        result = {'good': [], 'bad': [], 'minions': 0, 'servants': 0, 'all': []}

        for character in self.character_list:
            result['all'].append(character)
            if character.good:
                result['good'].append(character)
            else:
                result['bad'].append(character)

        result['minions'] = required_bad_characters - len(result['bad'])
        result['servants'] = required_good_characters - len(result['good'])

        for x in range(0, result['servants']):
            result['all'].append(Character.Servant)

        for x in range(0, result['minions']):
            result['all'].append(Character.Minion)

        return result