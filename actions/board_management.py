from botcommands.models import GameStage


def next_move(game):
    message = None
    if game.game_stage == GameStage.ChooseQuest:
        message = f"{game.player_list[game.player_turn_index].username_link()}, it is your turn to pick {game.get_quester_count()} players to go on a quest."
    elif game.game_stage == GameStage.VoteOnQuest:
        message = f"Everyone, it is your turn to vote on the quest."
    elif game.game_stage == GameStage.CompleteQuest:
        players = []
        for p in game.proposed_quest['players']:
            players.append(p.username_link())
        message = f"{', '.join(players)}, you have been sent on a quest."
    elif game.game_stage == GameStage.Assassinate:
        message = "*Assassin*, choose who to assassinate!"
    elif game.game_stage == GameStage.Won:
        message = "*GAME OVER*\n*Good Triumphs!*"
    elif game.game_stage == GameStage.Lost:
        message = "*GAME OVER*\n*Evil Triumphs!*"
    if not message:
        return None

    return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": message
            }
        }

def push_down():
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Push Down"
                },
                "value": "push_down",
                "action_id": "push_down"
            }
        ]
    }

def assassinate(game):
    return {
        "type": "actions",
        "elements": [
            {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Choose Assassination Target"
                },
                "action_id": "toggle_assassination_target",
                "options": game.get_player_quest_options()
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Assassinate"
                },
                "value": "assassinate",
                "action_id": "assassinate"
            }
        ]
    }

def game_over(game):
    return None
    # return {
    #         "type": "section",
    #         "text": {
    #             "type": "mrkdwn",
    #             "text": "*GAME OVER*"
    #         }
    #     }


def choose_quest(game):
    return {
        "type": "actions",
        "elements": [
            {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Choose players"
                },
                "action_id": "toggle_quest_user",
                "options": game.get_player_quest_options()
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Send Quest"
                },
                "value": "send_quest",
                "action_id": "send_quest"
            }
        ]
    }


def complete_quest():
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Succeed Quest"
                },
                "value": "succeed_quest",
                "action_id": "succeed_quest"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Fail Quest"
                },
                "value": "fail_quest",
                "action_id": "fail_quest"
            }
        ]
    }


def vote():
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Approve Quest"
                },
                "value": "approve_quest",
                "action_id": "approve_quest"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Reject Quest"
                },
                "value": "reject_quest",
                "action_id": "reject_quest"
            }
        ]
    }


def game_info(game):
    quest_results = ''
    for key in range(0, 5):
        temp = f"{key + 1})"
        if key > game.round or (key == game.round and game.game_stage not in (GameStage.Assassinate, GameStage.Lost, GameStage.Won)):
            quest_results = quest_results + "\n" + f"_{temp} {game.get_quester_count(round=key)} questers_"
        else:
            passed, success, fails = game.count_quest(key)
            quest_results = quest_results + "\n" + f"*{temp} {('Passed' if passed else 'Failed')}* _({success}-{fails})_"

    return {
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": "*Turn Order*\n" + "\n".join(list(map(
                    lambda x: "_" + ("*" if x.turn_order == game.player_turn_index else '') + x.username_link() + (
                        "*" if x.turn_order == game.player_turn_index else '') + "_", game.player_list)))
            },
            {
                "type": "mrkdwn",
                "text": "*Quests*" + quest_results
            }
        ]
    }

def quest_participants(game):
    return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ", ".join(list(map(lambda x: x.username_link(),
                                           game.proposed_quest['players']))) +
                        f" {'are' if len(game.proposed_quest['players']) > 1 else 'is'} {'tentatively ' if game.game_stage == GameStage.ChooseQuest else ''}proposed to go on the quest."
            }
        }


def admin(game):
    return {
        "type": "actions",
        "elements": [
            {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Act As"
                },
                "action_id": "toggle_admin_act_as",
                "options": game.get_player_quest_options()
            }
        ]
    }

def info(game):
    return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": game.message
            }
        }

def divider():
    return {
            "type": "divider"
        }


def get_game_board(game):
    sections = [
        admin(game) if game.debug else None,
        next_move(game),
        divider(),

        quest_participants(game) if game.game_stage in [GameStage.VoteOnQuest, GameStage.ChooseQuest] else None,

        vote() if game.game_stage == GameStage.VoteOnQuest
        else complete_quest() if game.game_stage == GameStage.CompleteQuest
        else choose_quest(game) if game.game_stage == GameStage.ChooseQuest
        else assassinate(game) if game.game_stage == GameStage.Assassinate
        else game_over(game),

        divider(),
        game_info(game),
        info(game) if game.message else None,
        push_down()
    ]
    sections = list(filter(None, sections))
    return sections


