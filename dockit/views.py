from os import statvfs, uname
import time
from socket import socket
import psutil
import uuid
import json
import requests
import subprocess
from django.shortcuts import render, HttpResponse, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseRedirect, StreamingHttpResponse, Http404
from dockit.models import User, IP, Image, Container
from dockit.forms import UserForm, IPForm, ContainerForm
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from django.views.decorators.http import condition
from docker_box.settings import BASE_DIR, DOCKER_API_PORT, HOST_IP_ADDR


def admin_required(function):
    def check_admin(request, *args, **kwargs):
        if not request.user.is_superuser:
            return render(request, 'no_access.html')
        return function(request, *args, **kwargs)
    return check_admin


def index(request):
    if request.method == "POST":
        user = authenticate(username=request.POST.get('email'), password=request.POST.get('password'))
        if user is not None:
            if user.is_active:
                login(request, user)
                return HttpResponseRedirect(request.GET.get('next') or '/')
            else:
                response_data = {'message': "Your account has been disabled!"}
        else:
            response_data = {'message': 'The username and password are incorrect.'}
        return render(request, 'login.html', response_data)

    elif request.user.is_authenticated():
        host_name, kernel = uname()[1:3]
        return render(request, 'dashboard.html', {'host_name': host_name, 'kernel': kernel, 'ip_addr': HOST_IP_ADDR})

    else:
        return render(request, 'login.html')


def logout_user(request):
    if request.user.is_authenticated():
        logout(request)
    return HttpResponseRedirect('/')


@login_required
@condition(etag_func=None)
def host_stats(request):
    return StreamingHttpResponse(stream_host_stats())


def stream_host_stats():
    while True:
        net = psutil.net_io_counters(pernic=True)
        time.sleep(1)
        net1 = psutil.net_io_counters(pernic=True)
        net_stat_download = {}
        net_stat_upload = {}
        for k, v in net.items():
            for k1, v1 in net1.items():
                if k1 == k:
                    net_stat_download[k] = (v1.bytes_recv - v.bytes_recv) / 1000.
                    net_stat_upload[k] = (v1.bytes_sent - v.bytes_sent) / 1000.
        ds = statvfs('/')
        disk_str = {"Used": ((ds.f_blocks - ds.f_bfree) * ds.f_frsize) / 10 ** 9, "Unused": (ds.f_bavail * ds.f_frsize) / 10 ** 9}
        yield '[{"cpu":"%s","memory":"%s","memTotal":"%s","net_stats_down":"%s","net_stats_up":"%s","disk":"%s"}],' \
              % (psutil.cpu_percent(interval=1), psutil.virtual_memory().used, psutil.virtual_memory().free, \
                 net_stat_download, net_stat_upload, disk_str)


@login_required
@admin_required
def docker_images(request):
    images = Image.objects.filter(snapshot=None, is_snapshot=False)
    uuid_token = str(uuid.uuid4())
    return render(request, "images_list.html", {'images': images, 'uuid_token': uuid_token})


@login_required
def launch_image(request, name):
    image = Image.objects.get(name=name)
    if image.has_access(request.user):
        if request.method == "POST":
            container_form = ContainerForm(request.POST, ssh_users=request.POST.getlist('ssh_users'))
            if container_form.is_valid():
                memory, cores, hostname = container_form.cleaned_data['ram'], \
                    container_form.cleaned_data['cores'], \
                    container_form.cleaned_data['hostname']
                image_obj = Image.objects.get(id=request.POST['image'])
                container_obj = container_form.save(commit=False)
                if container_obj.ip.is_routed:
                    result = image_obj.run_bridge(cores, memory, container_obj.ip.ip_addr, hostname)
                else:
                    result = image_obj.run_macvlan(cores, memory, container_obj.ip.ip_addr, container_obj.ip.mac_addr, hostname)
                container_obj.container_id = result
                container_obj.save()
                for r in request.POST.getlist('user'):
                    container_obj.user.add(r)
                container_obj.save()

                for ssh_user in request.POST.getlist('ssh_users'):
                    user_obj = User.objects.get(email=ssh_user)
                    container_obj.copy_ssh_pub_key(user_obj)

                passphrase = container_obj.set_passphrase()
                request.session['launched_container_id'] = container_obj.container_id.decode('utf-8')
                ip = IP.objects.get(ip_addr=str(container_obj.ip))
                ip.is_available = False
                ip.save()
                url = reverse('docker_box:container_info', kwargs={'container_id': container_obj.container_id.decode('utf-8')})
                return JsonResponse({'success': 'image launched', 'url': url, 'passphrase': passphrase})

            return JsonResponse({'FORM_ERRORS': 'true', 'form_errors': container_form.errors})
        else:
            users = [request.user]
            if request.user.is_superuser:
                users = User.objects.filter(is_active=True)
                images = Image.objects.all()
            else:
                images = Image.objects.filter(user=request.user)
            ips = IP.objects.filter(is_active=True, is_available=True)

            return render(request, "launch_image.html", {'ips': ips, 'images': images, 'image_name': name, 'users': users})
    raise PermissionDenied


@login_required
def container_list(request):
    if request.user.is_superuser:
        containers = Container.objects.all()
    else:
        containers = Container.objects.filter(user=request.user)
    active_containers_list = []
    idle_containers_list = []
    for container in containers:
        details_d = container.details()
        container.__dict__.update(details_d)
        if details_d['running']:
            active_containers_list.append(container)
        else:
            idle_containers_list.append(container)

    return render(
        request,
        "container_list.html",
        {
            'active_containers_list': active_containers_list,
            'idle_containers_list': idle_containers_list
        }
    )


@login_required
def container_details(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        images = Image.objects.filter(user=request.user, snapshot=container, is_snapshot=True)
        return render(request, "container_details.html", {"container": container.json(), 'data': \
                [['100', 10], ['90', 9], ['80', 8]], 'images': images, 'container_id': container.container_id})
    else:
        return render(request, 'no_access.html')


@login_required
@admin_required
def users_list(request):
    users = User.objects.all()
    return render(request, "users.html", {"users_list": users})


@login_required
@admin_required
def new_user(request):
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({"error": False})
        else:
            return JsonResponse({"error": True, "errors": form.errors})
    form = UserForm()
    return render(request, "new_user.html", {"form": form})


@login_required
@admin_required
def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return JsonResponse({"error": False})
        else:
            return JsonResponse({"error": True, "errors": form.errors})
    form = UserForm(instance=user)
    return render(request, "new_user.html", {"form": form})


@login_required
@admin_required
def delete_user(request, pk):
    get_object_or_404(User, pk=pk).delete()
    return redirect("docker_box:users-list")


@login_required
@admin_required
def ip_list(request):
    ip_list = IP.objects.filter(is_available=True)
    
    return render(request, "ip_address.html", {"ip_list": ip_list})


@login_required
@admin_required
def new_ip(request):
    request_post = request.POST.copy()
    if '0' in request_post['is_routed']:
        del request_post['is_routed']
    form = IPForm(request_post)
    if form.is_valid():
        form.save()
        return JsonResponse({"error": False})
    else:
        return JsonResponse({"error": True, "errors": form.errors})


@login_required
@admin_required
def edit_ip(request, pk):
    instance = get_object_or_404(IP, id=pk)
    if Container.objects.filter(ip=instance).exists():
        raise Http404
    else:
        form = IPForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return JsonResponse({"error": False})
        else:
            return JsonResponse({"error": True, "errors": form.errors})


@login_required
@admin_required
def delete_ip(request, pk):
    ip_obj = get_object_or_404(IP, id=pk)
    if Container.objects.filter(ip=ip_obj).exists():
        raise Http404
    else:
        get_object_or_404(IP, pk=pk).delete()
        return redirect("docker_box:ip-list")


@login_required
@admin_required
def search_images(request):
    term = request.POST['term']
    images = requests.get('http://localhost:' + DOCKER_API_PORT + '/images/search?term=' + term)
    return HttpResponse(json.dumps(images.json()),
                        content_type='application/json')


@login_required
@admin_required
def pull_image_progress(request, uuid_token):
    file = open('/tmp/' + uuid_token, 'r')
    data = file.read()
    file.close()
    if data:
        return JsonResponse(data, safe=False)
    else:
        return JsonResponse({"status": "Pulling Please wait..."})


@login_required
@admin_required
def pull_image(request, uuid_token):
    # TODO userdefined tag
    params = {'tag': 'latest', 'fromImage': request.POST['imageName']}
    response = requests.post('http://localhost:' + DOCKER_API_PORT + '/images/create', params=params, stream=True)
    if response:
        for line in response.iter_lines():
            file = open('/tmp/' + uuid_token, 'w')
            if line:
                output = json.loads(str(line.decode(encoding='UTF-8')))
                try:
                    if output['progressDetail']:
                        progress = (output['progressDetail']['current'] * 100) / output['progressDetail']['total']
                        file.write('{"status": "ok","image-status":"' + output['status'] + '","progress":' + str(
                            int(progress)) + ',"id":"' + output['id'] + '"}')
                except KeyError:
                    try:
                        if 'Digest:' in output['status']:
                            Image.objects.get_or_create(name=request.POST['imageName'], user=request.user, tag='latest')
                    except KeyError:
                        pass
                    file.close()
                    file = open('/tmp/progress', 'w')
                    file.write(str({"status": output['status']}))
        file.close()
        return JsonResponse({'status': 'ok'})
    else:
        return JsonResponse({'status': 'error'})


@login_required
def start_container(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        status_code = container.start()
        if status_code == 204:
            return JsonResponse({'success': 'started'})
        elif status_code == 304:
            return JsonResponse({'success': 'Already Started'})
        elif status_code == 404:
            return JsonResponse({'ERROR': 'No Such Container'})
        elif status_code == 500:
            return JsonResponse({'ERROR': 'Server Error'})
        else:
            return JsonResponse({'ERROR': 'ERROR STARTING CONTAINER'})
    else:
        return render(request, 'no_access.html')


@login_required
def stop_container(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        status_code = container.stop()
        if status_code == 204:
            response = {'success': 'stopped'}
        elif status_code == 304:
            response = {'success': 'stopped'}
        elif status_code == 404:
            response = {'ERROR': 'No Such Container'}
        elif status_code == 500:
            response = {'ERROR': 'Server Error'}
        else:
            response = {'ERROR': 'ERROR STOPPING CONTAINER'}
        return JsonResponse(response)
    else:
        return render(request, 'no_access.html')


@login_required
def restart_container(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        status_code = container.restart()
        if status_code == 204:
            return JsonResponse({'success': 'restarted'})
        elif status_code == 404:
            return JsonResponse({'ERROR': 'No Such Container'})
        elif status_code == 500:
            return JsonResponse({'ERROR': 'Server Error'})
        else:
            return JsonResponse({'ERROR': 'Error Restarting Container'})
    return render(request, 'no_access.html')


@login_required
@condition(etag_func=None)
def container_stats(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        return StreamingHttpResponse(stream_response_generator(container))
    return render(request, 'no_access.html')


def stream_response_generator(container):
    container_id = container.container_id
    while True:
        response = str(subprocess.check_output("docker stats --no-stream " + container_id + "| tail -1", shell=True))
        response = response.split()
        if response:
            yield '[{"cpu":"%s","memory":"%s","memTotal":"%s","netDow":"%s","netDowUnit":"%s",\
                    "netUp":"%s","netUpUnit":"%s"}],' % (response[1], response[7], response[5], \
                    response[8], response[9], response[11], response[12])
        else:
            yield response


@login_required
def backup_container(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if request.POST:
        if container:
            name = request.POST['name']
            if Image.objects.filter(user=request.user, name=name).exists():
                return JsonResponse({'error': True, 'msg': 'Image with this name exists.'})
            else:
                status_code, response_json = container.commit(name)
                if status_code == 201:
                    Image.objects.create(name=name, tag='latest', user=request.user, snapshot=container, is_snapshot=True)
                    return JsonResponse({'error': False, 'image_id': response_json['Id']})
        return render(request, 'no_access.html')
    else:
        return render(request, 'backup_container.html')


@login_required
def change_password(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        passphrase = container.set_passphrase()
        return JsonResponse({'error': False, 'passphrase': passphrase})
    return render(request, 'no_access.html')


@login_required
def ssh_access(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        if request.POST:
            ssh_users = request.POST.getlist('ssh_users')
            for ssh_user in ssh_users:
                user_obj = User.objects.get(email=ssh_user)
                if not user_obj.ssh_pub_key:
                    return JsonResponse({'error': True})
            for ssh_user in ssh_users:
                user_obj = User.objects.get(email=ssh_user)
                container.copy_ssh_pub_key(user_obj)
            return JsonResponse({'error': False})
        users = [request.user]
        if request.user.is_superuser:
            users = User.objects.filter(is_active=True)
        return render(request, 'ssh_access.html', {'users': users})
    return render(request, 'no_access.html')


@login_required
def container_top(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        top = container.top()
        if top:
            return JsonResponse(top)
        return JsonResponse({'Titles': None, 'Processes': None})
    return render(request, 'no_access.html')


@login_required
def container_diff(request, container_id, total):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        diff = container.diff()
        modified = []
        added = []
        deleted = []
        for file_info in diff:
            if file_info['Kind'] == 0:
                modified.append(file_info['Path'])
            elif file_info['Kind'] == 1:
                added.append(file_info['Path'])
            elif file_info['Kind'] == 2:
                deleted.append(file_info['Path'])

        if total == '0':
            return JsonResponse({'modified': modified[:10], 'added': added[:10], 'deleted': deleted[:10]})
        return JsonResponse({'modified': modified, 'added': added, 'deleted': deleted})
    return render(request, 'no_access.html')


def find_free_port():
    s = socket()
    s.bind(('', 0))
    return s.getsockname()[1]


@login_required
def terminal(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        port = find_free_port()
        uuid_token = str(uuid.uuid4())
        go_cmd = './dockit/terminal %s %s %s %s %s' % (port, HOST_IP_ADDR, DOCKER_API_PORT, container_id, BASE_DIR)
        ncp_proc = subprocess.Popen(go_cmd, shell=True, executable='/bin/bash')
        return JsonResponse({'container_id': container_id, 'port': port})
    return render(request, 'no_access.html')


@login_required
def container_info(request, container_id):
    if request.POST:
        container = Container.objects.get_container(container_id, request.user)
        if container:
            details_d = container.details()
            container.__dict__.update(details_d)
            passphrase = request.POST['passphrase']
            return render(request, 'container_info.html', {'container': container, 'passphrase': passphrase})
    return render(request, 'no_access.html')


@login_required
def remove_image(request, name):
    image = Image.objects.get_image(name, request.user)
    if image:
        if request.POST:
            passphrase = request.POST['passphrase']
            if request.user.check_password(passphrase):
                status_code = image.remove()
                if status_code == 200:
                    image.delete()
                    return JsonResponse({'success': 'Deleted'})
                elif status_code == 404:
                    return JsonResponse({'ERROR': 'NO SUCH IMAGE'})
                elif status_code == 409:
                    return JsonResponse({'ERROR': 'Image Conflict'})
                return JsonResponse({'ERROR': 'Unable to remove image'})
            return JsonResponse({'perror': True})
        else:
            details_d = image.details()
            image.__dict__.update(details_d)
            return render(request, 'remove_image.html', {'image': image})
    return render(request, 'no_access.html')


@login_required
def edit_container(request, container_id):
    container_instance = get_object_or_404(Container, container_id=container_id)
    if container_instance:
        if request.POST:
            container_form = ContainerForm(request.POST, instance=container_instance, ssh_users=request.POST.getlist('ssh_users'))
            if container_form.is_valid():
                container_obj = container_form.save(commit=False)
                container_obj.save()
                container_obj.user.clear()
                for r in request.POST.getlist('user'):
                    container_obj.user.add(r)
                container_obj.save()

                for ssh_user in request.POST.getlist('ssh_users'):
                    user_obj = User.objects.get(email=ssh_user)
                    container_obj.copy_ssh_pub_key(user_obj)
                url = reverse('docker_box:container-list')
                return JsonResponse({'success': 'image launched', 'url': url})

            return JsonResponse({'FORM_ERRORS': 'true', 'form_errors': container_form.errors})
        else:
            users = [request.user]
            if request.user.is_superuser:
                users = User.objects.filter(is_active=True)
                images = Image.objects.all()
            else:
                images = Image.objects.filter(user=request.user)
            ips = IP.objects.filter(is_active=True)
            container_details = container_instance.details()
            container_instance.__dict__.update(container_details)

            return render(request, "launch_image.html", {'edit_container': container_instance, 'ips': ips, 'images': images, 'users': users})
    return render(request, 'no_access.html')


@login_required
def delete_container(request, container_id):
    container = Container.objects.get_container(container_id, request.user)
    if container:
        if request.POST:
            passphrase = request.POST['passphrase']
            if request.user.check_password(passphrase):
                status_code = container.remove()
                if status_code == 204:
                    ip_obj = container.ip
                    ip_obj.is_available = True
                    ip_obj.save()
                    container.delete()
                    response = {'success': 'Deleted'}
                elif status_code == 400:
                    response = {'ERROR': 'Bad Parameter'}
                elif status_code == 404:
                    response = {'ERROR': 'No Such Container'}
                elif status_code == 500:
                    response = {'ERROR': 'Server Error'}
                elif status_code == 409:
                    response = {'ERROR': 'Stop container before deletion.'}
                else:
                    response = {'ERROR': 'Unable to remove container'}
                return JsonResponse(response)
            return JsonResponse({'perror': True})
        else:
            details_d = container.details()
            container.__dict__.update(details_d)
            return render(request, 'remove_container.html', {'container': container})
    return render(request, 'no_access.html')
