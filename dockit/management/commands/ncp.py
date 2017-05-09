from optparse import make_option
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sessions.models import Session
from django.http import HttpResponseForbidden
from dockit.models import User, Container

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('container_id', nargs='+', type=str)
        parser.add_argument('sessionid', nargs='+', type=str)

    def handle(self, *args, **options):
        try:
            sessionid = options['sessionid'][0].rstrip()
            session = Session.objects.get(session_key=str(sessionid))
            uid = session.get_decoded().get('_auth_user_id')
            user = User.objects.get(id=uid)
            container = Container.objects.get(container_id=options['container_id'][0])
        except ObjectDoesNotExist as e:
            raise HttpResponseForbidden
        else:
            if user.is_superuser or container.user == user:
                pass
            else:
                raise HttpResponseForbidden
