from django.views.decorators.csrf import csrf_exempt

from django.conf.urls.defaults import patterns, url

from mozdns.txt.views import (TXTListView, TXTCreateView,
                              TXTUpdateView, TXTDeleteView,
                              TXTDetailView)

urlpatterns = patterns('',
                       url(r'^$', TXTListView.as_view()),
                       url(r'(?P<domain>[\w-]+)/create/$',
                           csrf_exempt(TXTCreateView.as_view())),
                       url(r'create/$', csrf_exempt(TXTCreateView.as_view())),
                       url(r'(?P<pk>[\w-]+)/update/$',
                           csrf_exempt(TXTUpdateView.as_view())),
                       url(r'(?P<pk>[\w-]+)/delete/$',
                           csrf_exempt(TXTDeleteView.as_view())),
                       url(r'(?P<pk>[\w-]+)/$',
                           csrf_exempt(TXTDetailView.as_view())),
                       )
