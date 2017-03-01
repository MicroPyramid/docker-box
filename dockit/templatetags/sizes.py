import datetime
from django import template
import requests
from dockit.utils import DHost
from django.conf import settings
from dateutil import parser

register = template.Library()


@register.filter
def bytes_to_mb(bytes):
    return format(bytes / 1024 / 1024, '.2f')


@register.filter
def remove_slash(string):
    return string.replace("/", "")


@register.filter
def epoch_to_datetime(epoch):
    date_time = datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')
    # TODO: humanize should work based on loggedin user's timezone.
    return date_time


@register.filter
def container_ram(container_id):
    container = requests.get('http://localhost:' + settings.DOCKER_API_PORT + '/containers/' + container_id + '/json')
    return format(container.json()['HostConfig']['Memory'] / 1024 / 1024, '.0f')


@register.filter
def container_cores(container_id):
    container = requests.get('http://localhost:' + settings.DOCKER_API_PORT + '/containers/' + container_id + '/json')
    if container.json()['HostConfig']['CpusetCpus']:
        return len([a for a in container.json()['HostConfig']['CpusetCpus'].split(',')])
    return None


@register.assignment_tag
def host_cores():
    return DHost.cpu('count')


@register.assignment_tag
def host_ram_in_mb():
    return DHost.memory('total')


@register.filter
def convert_to_date_obj(date_string):
    date_obj = parser.parse(date_string)
    return date_obj


@register.filter
def split(string, split_char):
    return string.split(split_char)
