from random import sample as random_sample
from psutil import cpu_count
from django import forms
from dockit.models import User, IP, Container
from .utils import DHost


class UserForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            if field == "is_active":
                continue
            self.fields[field].widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        instance = super(UserForm, self).save(commit=False)
        if commit:
            instance.save()
        if self.cleaned_data.get("password"):
            instance.set_password(self.cleaned_data.get("password"))
            instance.save()

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not (self.instance.id or password):
            raise forms.ValidationError("Please provide password")
        return password

    password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ("email", "username", "is_active", "password", "ssh_pub_key")


class IPForm(forms.ModelForm):

    class Meta:
        model = IP
        exclude = []


class ContainerForm(forms.ModelForm):
    ram = forms.IntegerField(required=False)
    cores = forms.IntegerField(required=False)
    class Meta:
        model = Container
        fields = ('hostname', 'ip', 'image')

    def __init__(self, *args, **kwargs):
        self.ssh_users = kwargs.pop('ssh_users')
        super(ContainerForm, self).__init__(*args, **kwargs)
        if 'edit_field' in self.data.keys():
            self.fields['hostname'].required = False
            self.fields['ip'].required = False
            self.fields['image'].required = False

    def clean(self):
        ram = self.cleaned_data.get('ram', None)
        cores = self.cleaned_data.get('cores', None)

        if cores:
            cores = random_sample(range(0, cpu_count()), cores)
            cores = ','.join(map(str, cores))
            self.cleaned_data['cores'] = cores
        else:
            cores = cpu_count()
            cores = str(list(range(0, cores))).strip('[]').replace(" ", "")
            self.cleaned_data['cores'] = cores

        if ram:
            ram = int(ram)
            self.cleaned_data['ram'] = ram
        else:
            ram = int(DHost.memory('total'))
            self.cleaned_data['ram'] = ram

        if self.ssh_users:
            for ssh_user in self.ssh_users:
                user_obj = User.objects.get(email=ssh_user)
                if not user_obj.ssh_pub_key:
                    raise forms.ValidationError("SSH key not found")
        return self.cleaned_data


class ContainerEditForm(forms.ModelForm):

    class Meta:
        model = Container
        fields = ('user',)

    def __init__(self, *args, **kwargs):
        self.ssh_users = kwargs.pop('ssh_users')
        super(ContainerForm, self).__init__(*args, **kwargs)


    def clean(self):
        if self.ssh_users:
            for ssh_user in self.ssh_users:
                user_obj = User.objects.get(email=ssh_user)
                if not user_obj.ssh_pub_key:
                    raise forms.ValidationError("SSH key not found")
        return self.cleaned_data

