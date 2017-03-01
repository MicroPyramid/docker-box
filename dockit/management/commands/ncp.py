from optparse import make_option
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sessions.models import Session
from django.http import HttpResponseForbidden
from dockit.models import User, Container

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (make_option('--container_id', action='store', \
            dest='container_id'), make_option('--sessionid', action='store', dest='sessionid'))

    def handle(self, *args, **options):
        try:
            sessionid = options['sessionid'].rstrip()
            session = Session.objects.get(session_key=str(sessionid))
            uid = session.get_decoded().get('_auth_user_id')
            user = User.objects.get(id=uid)
            container = Container.objects.get(container_id=options['container_id'])
        except ObjectDoesNotExist:
            #raise HttpResponseForbidden
            pass
        else:
            if user.is_superuser or container.user == user:
                pass
            else:
                raise HttpResponseForbidden
