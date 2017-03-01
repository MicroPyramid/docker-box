from subprocess import check_output
from string import ascii_uppercase, digits
from random import SystemRandom
import psutil
import shutil
import requests
from django.conf import settings


class DHost(object):
    @classmethod
    def disk_size(self):
        x = shutil.disk_usage('/')
        return format(x.total / 1024 / 1024 / 1024, '.2f')

    @classmethod
    def free_space(self):
        x = shutil.disk_usage('/')
        return format(x.free / 1024 / 1024 / 1024, '.2f')

    @classmethod
    def used_space(self):
        x = shutil.disk_usage('/')
        return format(x.used / 1024 / 1024 / 1024, '.2f')

    @classmethod
    def net_inbound(self):
        return "3"

    @classmethod
    def net_outbound(self):
        return "3"

    @classmethod
    def memory(self, type):
        mem = psutil.virtual_memory()
        if type == 'total':
            return format(mem.total / 1024 / 1024, '.0f')
        elif type == 'available':
            return format(mem.available / 1024 / 1024, '.0f')
        elif type == 'used':
            return format(mem.used / 1024 / 1024, '.0f')
        elif type == 'free':
            return format(mem.free / 1024 / 1024, '.0f')
        elif type == 'cached':
            return format(mem.cached / 1024 / 1024, '.0f')

    @classmethod
    def cpu(self, type):
        if type == 'count':
            return psutil.cpu_count()
        elif type == 'cpu_percent':
            return psutil.cpu_percent(interval=1)


class ImageMixin:
    def run_macvlan(self, cores, memory, ip_addr, mac_addr, hostname):
        #TODO implement with api, or handle exception
        run_cmd = 'docker run --cpuset-cpus=%s -m %sM --net=dbox_macvlan \
                --ip=%s --mac-address %s -h %s -itd %s' % (cores, memory, \
                ip_addr, mac_addr, hostname, self.name)
        return check_output(run_cmd, shell=True)[0:12]

    def run_bridge(self, cores, memory, ip_addr, hostname):
        #TODO implement with api, or handle exception
        run_cmd = 'docker run --cpuset-cpus=%s -m %sM --net=dbox_bridge \
                --ip=%s -h %s -itd %s' % (cores, memory, ip_addr, hostname, self.name)
        return check_output(run_cmd, shell=True)[0:12]

    def remove(self):
        response = requests.delete('http://localhost:' + settings.DOCKER_API_PORT + '/images/' + self.name)
        return response.status_code

    def details(self):
        encode_name = self.name.replace('/', '%2F')
        details_rg = requests.get('http://localhost:%s/images/%s:%s/json' % (settings.DOCKER_API_PORT, encode_name, self.tag))
        j_details = details_rg.json()
        details_d = {'size': j_details['Size'] / 1000000, 'created': j_details['Created'].split('.')[0].replace('T', ' ')}
        return details_d

    def image_id(self):
        encode_name = self.name.replace('/', '%2F')
        response = requests.get('http://localhost:%s/images/%s:%s/json' % (settings.DOCKER_API_PORT, encode_name, self.tag))
        return response.json()['Id']

    def has_access(self, user):
        if user.is_superuser or self.user == user:
            return True
        else:
            return False


class ContainerMixin:
    def has_access(self, user):
        if user.is_superuser or self.user == user:
            return True
        else:
            return False

    def start(self):
        if isinstance(self.container_id, bytes):
            container_id = self.container_id.decode("utf-8")
        else:
            container_id = self.container_id
        response = requests.post('http://localhost:' + settings.DOCKER_API_PORT + \
                '/containers/' + container_id + '/start')
        return response.status_code

    def stop(self):
        if isinstance(self.container_id, bytes):
            container_id = self.container_id.decode("utf-8")
        else:
            container_id = self.container_id
        response = requests.post('http://localhost:' + settings.DOCKER_API_PORT + \
                '/containers/' + container_id + '/stop')
        return response.status_code

    def restart(self):
        response = requests.post('http://localhost:' + settings.DOCKER_API_PORT + \
                '/containers/' + self.container_id + '/restart')
        return response.status_code

    def remove(self):
        response = requests.delete('http://localhost:' + settings.DOCKER_API_PORT + \
                '/containers/' + self.container_id + '?v=1?force=1')
        return response.status_code

    def details(self):
        details_rg = requests.get('http://localhost:' + settings.DOCKER_API_PORT + \
                '/containers/' + self.container_id + '/json')
        j_details = details_rg.json()
        details_d = {'memory': j_details['HostConfig']['Memory']/1000000}
        details_d['cores'] = j_details['HostConfig']['CpusetCpus']

        net = j_details['NetworkSettings']['Networks']
        if net.get('dbox_macvlan', None):
            details_d['ip_addr'] = net['dbox_macvlan']['IPAddress']
        else:
            details_d['ip_addr'] = net['dbox_bridge']['IPAddress']

        details_d['created'] = j_details['Created'].split('.')[0].replace('T', ' ')
        details_d['running'] = j_details['State']['Running']
        return details_d

    def running_processes(self):
        processes = requests.get('http://localhost:' + settings.DOCKER_API_PORT + '/containers/' + self.container_id + '/top')
        return processes

    def json(self):
        container = requests.get('http://localhost:' + settings.DOCKER_API_PORT + '/containers/' + self.container_id + '/json')
        return container.json()

    def commit(self, name):
        params = {'container': self.container_id, 'repo': name, 'tag': 'latest'}
        response = requests.post('http://localhost:%s/commit' % (settings.DOCKER_API_PORT), params=params)
        return response.status_code, response.json()

    def set_passphrase(self):
        symbols = '!@#%^&*_-=;:?><,.'
        passphrase = ''.join(SystemRandom().choice(ascii_uppercase+digits+symbols) for _ in range(15))
        if type(self.container_id) == str:
            cmd = r'''docker exec %s bash -c "echo root:$'%s' | chpasswd"''' % (self.container_id, passphrase)
        else:
            cmd = r'''docker exec %s bash -c "echo root:$'%s' | chpasswd"''' % (self.container_id.decode("utf-8"), passphrase)
        check_output(cmd, shell=True)
        return passphrase

    def copy_ssh_pub_key(self, user):
        ssh_pub_key = user.ssh_pub_key
        if type(self.container_id) == str:
            cmd = r'''docker exec %s bash -c "ls /root/.ssh || mkdir /root/.ssh && echo '%s' >> /root/.ssh/authorized_keys"''' \
                    % (self.container_id, ssh_pub_key)
        else:
            cmd = r'''docker exec %s bash -c "ls /root/.ssh || mkdir /root/.ssh && echo '%s' >> /root/.ssh/authorized_keys"''' \
                    % (self.container_id.decode('utf-8'), ssh_pub_key)
        check_output(cmd, shell=True)

    def top(self):
        top_rg = requests.get('http://localhost:' + settings.DOCKER_API_PORT + '/containers/%s/top' % (self.container_id))
        if top_rg.status_code == 200:
            return top_rg.json()
        return None

    def diff(self):
        diff_rg = requests.get('http://localhost:' + settings.DOCKER_API_PORT + '/containers/%s/changes' % (self.container_id))
        if diff_rg.status_code == 200:
            return diff_rg.json()
        return []
