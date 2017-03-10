from django.conf.urls import url, include
from django.contrib import admin
from django.conf import settings
from django.views.static import serve as static_serve

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^', include('dockit.urls', namespace='docker_box')),    
]

urlpatterns += [
    url(r'^static/(?P<path>.*)$', static_serve, {'document_root': settings.STATIC_ROOT}),
]
