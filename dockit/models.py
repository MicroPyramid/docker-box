from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, UserManager, PermissionsMixin
from dockit.utils import ImageMixin, ContainerMixin
from django.core.exceptions import ObjectDoesNotExist


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, verbose_name="Name")
    username = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    ssh_pub_key = models.TextField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    def __str__(self):
        return self.email

    def get_short_name(self):
        """Return the email."""
        return self.email


class IP(models.Model):
    ip_addr = models.GenericIPAddressField(unique=True)
    mac_addr = models.CharField(max_length=200, null=True, blank=True)
    is_routed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.ip_addr


class Host(models.Model):
    hostname = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    ssh_port = models.CharField(max_length=10, default='22')
    docker_api_port = models.CharField(max_length=10)
    docker_network = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.ip.ip_addr


class ImageManager(models.Manager):
    def get_image(self, name, user):
        try:
            image = Image.objects.get(name=name)
            if user == image.user or user.is_superuser:
                return image
            else:
                return None
        except ObjectDoesNotExist:
            return None

class Image(models.Model, ImageMixin):
    name = models.CharField(max_length=200)
    tag = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    snapshot = models.ForeignKey('dockit.Container', models.SET_NULL, blank=True, null=True, related_name='backup')
    is_snapshot = models.BooleanField(default=False)
    objects = ImageManager()

    def __str__(self):
        return self.name


class ContainerManager(models.Manager):
    def get_container(self, container_id, user):
        try:
            container = Container.objects.get(container_id=container_id)
            if user == container.user or user.is_superuser:
                return container
            else:
                return None
        except ObjectDoesNotExist:
            return None


class Container(models.Model, ContainerMixin):
    hostname = models.CharField(max_length=100)
    container_id = models.CharField(max_length=200)
    image = models.ForeignKey(Image)
    ip = models.ForeignKey(IP)
    user = models.ManyToManyField(User)
    objects = ContainerManager()

    def __str__(self):
        return self.container_id
