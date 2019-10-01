from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from slack import WebClient

SLACK_VERIFICATION_TOKEN = getattr(settings, 'SLACK_VERIFICATION_TOKEN', None)
SLACK_BOT_USER_TOKEN = getattr(settings,  # 2
                               'SLACK_BOT_USER_TOKEN', None)  #
Client = WebClient(SLACK_BOT_USER_TOKEN)  # 3


class Events(APIView):

    def post(self, request, *args, **kwargs):

        slack_message = request.data

        if slack_message.get('token') != SLACK_VERIFICATION_TOKEN:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # verification challenge
        if slack_message.get('type') == 'url_verification':
            return Response(data=slack_message,
                            status=status.HTTP_200_OK)

        # greet bot
        if 'event' in slack_message:  # 4
            event_message = slack_message.get('event')  #

            # ignore bot's own message
            if event_message.get('subtype') == 'bot_message':  # 5
                return Response(status=status.HTTP_200_OK)  #

            # process user's message
            user = event_message.get('user')  # 6
            text = event_message.get('text')  #
            channel = event_message.get('channel')  #
            bot_text = 'Hi <@{}> :wave:'.format(user)  #
            if 'hi' in text.lower():  # 7
                Client.chat_postMessage(channel=channel,  #
                                text=bot_text)  #
                return Response(status=status.HTTP_200_OK)  # 9

        return Response(status=status.HTTP_200_OK)

