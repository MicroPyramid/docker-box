import json
import os
import requests
import time

from django.test import TestCase, Client
from django.core.urlresolvers import reverse

from dockit.views import stream_host_stats
from dockit.models import User, IP, Image, Container


class TestIndexView(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=False
        )
        self.password = "secret"
        self.user.set_password(self.password)
        self.user.save()

    def test_user_login(self):
        url = reverse("docker_box:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login.html")

        response = self.client.post(url, {})
        message = 'The username and password are incorrect.'
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["message"], message)

        credentials = {"email": self.user.email, "password": self.password}
        response = self.client.post(url, credentials)
        self.assertEqual(response.status_code, 302)

        # inactive user login
        self.user.is_active = False
        self.user.save()

        response = self.client.post(url, credentials)
        message = "Your account has been disabled!"
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["message"], message)

    def test_logged_in_user(self):
        url = reverse("docker_box:index")
        login = self.client.login(username=self.user.email, password=self.password)
        self.assertTrue(login)
        response = self.client.get(url)
        self.assertTemplateUsed(response, "dashboard.html")


class TestLogoutUserView(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=False
        )
        self.password = "secret"
        self.user.set_password(self.password)
        self.user.save()

    def test_logout_user(self):
        login = self.client.login(username=self.user.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:logout")
        response = self.client.get(url)
        self.assertFalse(response.context)
        self.assertEqual(response.status_code, 302)


class TestUsersListView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.user = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=False
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.user.set_password(self.password)
        self.user.save()


    def test_users_list(self):
        url = reverse("docker_box:users-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        login = self.client.login(username=self.user.email, password=self.password)
        response = self.client.get(url)
        self.assertTrue(login)
        self.assertTemplateUsed(response, "no_access.html")

        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users.html")


class TestNewUserView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=True,
            is_admin=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()

    def test_new_user(self):
        url = reverse("docker_box:new-user")
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "new_user.html")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("error"))
        data = {
            "email": "daniel@micropyradmic.com",
            "first_name": "Daniel",
            "is_active": True,
            "password": "secret"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get("error"))
        self.assertEqual(User.objects.count(), 2)


class TestEditUserView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=True,
            is_admin=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.user = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel"
        )

    def test_edit_user(self):
        url = reverse("docker_box:edit-user", kwargs={"pk": self.user.id})
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "new_user.html")
        
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("error"))
        
        data = {
            "email": "daniel.danny@micropyradmid.com",
            "first_name": "Daniel",
            "is_active": False,
            "password": "secret"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get("error"))
        self.assertFalse(User.objects.get(id=self.user.id).is_active)


class TestDeleteUserView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=True,
            is_admin=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.user = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel"
        )

    def test_delete_user(self):
        url = reverse("docker_box:delete-user", kwargs={"pk": self.user.id})

        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        response = self.client.get(url)
        redirect_url = reverse("docker_box:users-list")
        self.assertRedirects(response, redirect_url, 302)
        self.assertEqual(User.objects.count(), 1)


class TestHostStatsView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=True,
            is_admin=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()

    def test_host_stats(self):
        url = reverse("docker_box:host_stats")
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        response = self.client.get(url)
        self.assertTrue(response.streaming)


class TestStreamHostStats(TestCase):

    def test_stream_host_stats(self):
        streaming_data = next(stream_host_stats())
        l = json.loads(streaming_data[:-1])
        self.assertTrue(isinstance(l, list))


class TestDockerImagesView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule",
            is_superuser=True,
            is_admin=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.user = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )

    def test_docker_images(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:docker-images-list")
        response = self.client.get(url)
        self.assertEqual(list(response.context["images"]), list(Image.objects.all()))


class TestLaunchImageView(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel"
        )
        self.user2 = User.objects.create(
            email="sam@micropyramid.com",
            first_name="Daniel"
        )
        self.password = "secret"
        self.user.set_password(self.password)
        self.user.save()
        self.user2.set_password(self.password)
        self.user2.save()
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.user
        )

    def test_launch_image_no_permission(self):
        login = self.client.login(username=self.user2.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:launch-image", kwargs={"name": self.image.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_launch_image(self):
        login = self.client.login(username=self.user.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:launch-image", kwargs={"name": self.image.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)        
        self.assertTemplateUsed(response, "launch_image.html")     

        url = reverse("docker_box:launch-image", kwargs={"name": self.image.name})
        response = self.client.post(url, {})
        self.assertTrue(response.json().get("FORM_ERRORS"))

        data = {
            'hostname': "micropyramid.com",
            'ip': "10.10.2.25",
            'user': self.user.id,
            'image': "ubuntu-upstart"
        }
        response = self.client.post(url, data)

    def tearDown(self):
        super(TestLaunchImageView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestContainerStatsView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_container_stats(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:container_stats", kwargs=kwargs)
        response = self.client.get(url)
        self.assertTrue(response.streaming)

        kwargs = {"container_id": 152}
        url = reverse("docker_box:container_stats", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

    def tearDown(self):
        super(TestContainerStatsView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")



class TestPullImageProgressView(TestCase):

    def setUp(self):
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.uuid_token = "6a19ec28-db5f-4375-aeda-a5d15245d77c"
        self.file = open('/tmp/' + self.uuid_token, 'w')

    def test_pull_image_progress(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        kwargs = {"uuid_token": self.uuid_token}
        url = reverse("docker_box:pull-image-progress", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.file.write("abcd")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestPullImageView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.uuid_token = "6a19ec28-db5f-4375-aeda-a5d15245d77c"

    def test_pull_image(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:pull-image", kwargs={"uuid_token": self.uuid_token})
        response = self.client.post(url, {"imageName": "ubuntu-upstart"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})


class TestRemoveImage(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel"
        )
        self.user2 = User.objects.create(
            email="samule@micropyramid.com",
            first_name="Samule"
        )
        self.password = "secret"
        self.user.set_password(self.password)
        self.user.save()
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        requests.post('http://localhost:2375/images/create', params=params)
        params = {'tag': 'latest', 'fromImage': 'maven'}
        requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.user
        )
        self.image2 = Image.objects.create(
            name="ubuntupstart",
            tag="latest",
            user=self.user
        )
        self.image3 = Image.objects.create(
            name="ubuntu",
            tag="latest",
            user=self.user2
        )
        self.image4 = Image.objects.create(
            name="maven",
            tag="latest",
            user=self.user
        )

    def test_remove_image(self):
        login = self.client.login(username=self.user.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:remove_image", kwargs={"name": self.image.name})
        response = self.client.get(url)
        response = self.client.post(url, {"passphrase": self.password})
        self.assertTrue(response.json())

        url = reverse("docker_box:remove_image", kwargs={"name": self.image2.name})
        response = self.client.post(url, {"passphrase": self.password})
        self.assertEqual(response.json().get("ERROR"), "NO SUCH IMAGE")

        url = reverse("docker_box:remove_image", kwargs={"name": self.image4.name})
        response = self.client.post(url, {"passphrase": self.password})
        self.assertTrue(response.json())

        url = reverse("docker_box:remove_image", kwargs={"name": self.image4.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        super(TestRemoveImage, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")



class TestContainerListSuperUser(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )
        self.container.start()

    def test_container_list(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:container-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "container_list.html")

    def tearDown(self):
        super(TestContainerListSuperUser, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestContainerDetailsView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_container_details(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        kwargs={"container_id": 520}
        url = reverse("docker_box:container-details", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        kwargs={"container_id": self.container.container_id}
        url = reverse("docker_box:container-details", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "container_details.html")

    def tearDown(self):
        super(TestContainerDetailsView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestContainerInfoView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_container_info(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:container_info", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:container_info", kwargs=kwargs)
        response = self.client.post(url, {"passphrase": self.password})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "container_info.html")

    def tearDown(self):
        super(TestContainerInfoView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestContainerTop(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_container_top(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:top", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")
        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:top", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        super(TestContainerTop, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestRestartContainerView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_restart_container(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:ssh_access", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

    def tearDown(self):
        super(TestRestartContainerView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestSSHAccessView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )
        u1 = User(
            email="satran@mp.com",
            first_name="satran",
            ssh_pub_key="dummy ssh key1"
        )
        u2 = User(
            email="mars@mp.com",
            first_name="mars",
            ssh_pub_key="dummy ssh key2"
        )
        u3 = User(
            email="jupitor@mp.com",
            first_name="jupitor",
        )
        users_list = [u1, u2, u3]
        User.objects.bulk_create(users_list)

    def test_ssh_access(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:ssh_access", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        url = reverse("docker_box:ssh_access", kwargs={"container_id": self.container.container_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ssh_access.html")

        self.admin.is_superuser = False
        self.admin.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ssh_access.html")

        data = {"ssh_users": ["satran@mp.com", "mars@mp.com"]}
        response = self.client.post(url, data)
        self.assertFalse(response.json().get("error"))
        data = {"ssh_users": ["jupitor@mp.com"]}
        response = self.client.post(url, data)
        self.assertTrue(response.json().get("error"))

    def tearDown(self):
        super(TestSSHAccessView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestContainerDiffView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_container_diff(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        kwargs = {
            "container_id": 255,
            "total": "0"
        }
        url = reverse("docker_box:diff", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        kwargs = {
            "container_id": self.container.container_id,
            "total": "0"
        }
        url = reverse("docker_box:diff", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("deleted" in response.json())

    def test_container_diff_total(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        kwargs = {
            "container_id": self.container.container_id,
            "total": "2"
        }
        url = reverse("docker_box:diff", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("deleted" in response.json())


    def tearDown(self):
        super(TestContainerDiffView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestBackupContainerView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_backup_container(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:backup_container", kwargs={"container_id": 455})
        response = self.client.post(url, {"test": "test"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:backup_container", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "backup_container.html")

        response = self.client.post(url, {"name": self.image.name})
        self.assertTrue(response.json().get("error"))

        response = self.client.post(url, {"name": "custom_name"})
        self.assertFalse(response.json().get("error"))


    def tearDown(self):
        super(TestBackupContainerView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestChangePassword(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_change_password(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:change_password", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")
        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:change_password", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get("error"))

    def tearDown(self):
        super(TestChangePassword, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestTerminalView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_terminal(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:terminal", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")
        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:terminal", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("container_id" in response.json())


    def tearDown(self):
        super(TestTerminalView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestStartContainerView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_start_container(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:start-container", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:start-container", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': 'Already Started'})

        self.container.stop()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': 'started'})

    def tearDown(self):
        super(TestStartContainerView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestStopContainerView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_stop_container(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)

        url = reverse("docker_box:stop-container", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        kwargs = {"container_id": self.container.container_id}
        url = reverse("docker_box:stop-container", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': 'stopped'})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': 'stopped'})

    def tearDown(self):
        super(TestStopContainerView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestContainerDeleteView(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="79.137.106.65",
            is_active=True,
            is_available=True,
            mac_addr="68:5d:43:b9:83:b8"
        )
        params = {'tag': 'latest', 'fromImage': 'ubuntu-upstart'}
        response = requests.post('http://localhost:2375/images/create', params=params)
        self.image = Image.objects.create(
            name="ubuntu-upstart",
            tag="latest",
            user=self.admin
        )
        hostname = "micro.com"
        cores = "0,1"
        memory = "200"
        container_id = self.image.run(
            cores, memory, self.ip.ip_addr, self.ip.mac_addr, hostname
        )
        self.container = Container.objects.create(
            hostname=hostname,
            container_id=container_id,
            image=self.image,
            ip=self.ip,
            user=self.admin
        )

    def test_delete_container(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:delete_container", kwargs={"container_id": 520})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "no_access.html")

        url = reverse("docker_box:delete_container", kwargs={"container_id": self.container.container_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "remove_container.html")

        response = self.client.post(url, {"passphrase": "invalid"})
        self.assertTrue(response.json().get("perror"))

        response = self.client.post(url, {"passphrase": self.password})
        self.assertEqual(response.json(), {'ERROR': 'Stop container before deletion.'})

        self.container.stop()
        response = self.client.post(url, {"passphrase": self.password})
        self.assertEqual(response.json(), {'success': 'Deleted'})        

    def tearDown(self):
        super(TestContainerDeleteView, self).tearDown()
        os.system("docker kill $(docker ps -q)")
        os.system("docker rm $(docker ps -aq)")


class TestIPList(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        IP.objects.create(
            ip_addr="183.82.113.154",
            is_active=True,
            is_available=True
        )

    def test_ip_list(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:ip-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ip_address.html")
        self.assertEqual(IP.objects.count(), 1)


class TestNewIP(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()

    def test_new_ip(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:new-ip")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("error"))
        data = {
            "ip_addr":"183.82.113.154",
            "is_active":True,
            "is_available":True,
            "mac_addr": "FF:FF:FF:FF:FF:FF"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get("error"))
        self.assertEqual(IP.objects.count(), 1)


class TestEditIP(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="183.82.113.154",
            is_active=True,
            is_available=True
        )

    def test_edit_ip(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:edit-ip", kwargs={"pk": self.ip.id})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("error"))
        data = {
            "ip_addr":"183.82.113.154",
            "is_active":False,
            "is_available":True,
            "mac_addr": "FF:FF:FF:FF:FF:FF"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get("error"))
        self.assertFalse(IP.objects.get(id=self.ip.id).is_active)


class TestDeleteIP(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create(
            email="daniel@micropyramid.com",
            first_name="Daniel",
            is_admin=True,
            is_superuser=True
        )
        self.password = "secret"
        self.admin.set_password(self.password)
        self.admin.save()
        self.ip = IP.objects.create(
            ip_addr="183.82.113.154",
            is_active=True,
            is_available=True
        )

    def test_delete_ip(self):
        login = self.client.login(username=self.admin.email, password=self.password)
        self.assertTrue(login)
        url = reverse("docker_box:delete-ip", kwargs={"pk": self.ip.id})
        response = self.client.get(url)
        redirect_url = reverse("docker_box:ip-list")
        self.assertRedirects(response, redirect_url, 302)
        self.assertEqual(IP.objects.count(), 0)
