from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.contrib import messages
from django.forms.util import ErrorList, ErrorDict
from django.http import HttpResponse

from core.network.models import Network, NetworkKeyValue
from core.network.forms import *
from core.network.utils import calc_networks, calc_parent_str
from core.vlan.models import Vlan
from core.site.models import Site
from core.site.forms import SiteForm
from core.keyvalue.utils import get_attrs, update_attrs

from core.views import CoreDeleteView, CoreListView
from core.views import CoreCreateView
from mozdns.ip.models import ipv6_to_longs


import re
import pdb
import ipaddr

class NetworkView(object):
    model = Network
    queryset = Network.objects.all()
    form_class = NetworkForm

is_attr = re.compile("^attr_\d+$")

class NetworkDeleteView(NetworkView, CoreDeleteView):
    """ """

class NetworkListView(NetworkView, CoreListView):
    """ """
    template_name = 'network/network_list.html'

def create_network(request):
    if request.method == 'POST':
        form = NetworkForm(request.POST)
        try:
            if form.is_valid():
                network = form.instance
                if network.site is None:
                    parent = calc_parent(network)
                    if parent:
                        network.site = parent.site
                network.save()
            return redirect(network)
        except ValidationError, e:
            return render(request, 'core/core_form.html', {
                'object': network,
                'form': form,
            })
    else:
        form = NetworkForm()
        return render(request, 'core/core_form.html', {
            'form': form,
        })

def update_network(request, network_pk):
    network = get_object_or_404(Network, pk=network_pk)
    attrs = network.networkkeyvalue_set.all()
    aux_attrs = NetworkKeyValue.aux_attrs
    if request.method == 'POST':
        form = NetworkForm(request.POST, instance=network)
        try:
            if form.is_valid():
                # Handle key value stuff.
                kv = get_attrs(request.POST)
                update_attrs(kv, attrs, NetworkKeyValue, network, 'network')
                network = form.save()
            return redirect(network)
        except ValidationError, e:
            form = NetworkForm(instance=network)
            if form._errors is None:
                form._errors = ErrorDict()
            form._errors['__all__'] = ErrorList(e.messages)
            return render(request, 'network/network_edit.html', {
                'network': network,
                'form': form,
                'attrs': attrs,
                'aux_attrs': aux_attrs
            })

    else:
        form = NetworkForm(instance=network)
        return render(request, 'network/network_edit.html', {
            'network': network,
            'form': form,
            'attrs': attrs,
            'aux_attrs': aux_attrs
        })


def network_detail(request, network_pk):
    network = get_object_or_404(Network, pk=network_pk)
    network.update_network()
    attrs = network.networkkeyvalue_set.all()
    eldars, sub_networks = calc_networks(network)
    return render(request, 'network/network_detail.html', {
        'network': network,
        'eldars': eldars,
        'sub_networks': sub_networks,
        'attrs': attrs
        })

def do_network(request):
    form = NetworkForm_network()
    # return the allocate network block page.
    return render(request, 'network/network_form.html', {
        'form': form,
    })

def do_site(request, parent = None):
    form = NetworkForm_site()
    if parent:
        form.fields['site'].initial = parent
    else:
        form = SiteForm()
    # return the allocate network block page.
    return render(request, 'network/network_form.html', {
        'form': form,
    })

def do_vlan(request):
    form = NetworkForm_vlan()
    # return the allocate network block page.
    return render(request, 'network/network_form.html', {
        'form': form,
        'action': 'vlan',
    })

def network_wizard(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == "network":
            # return the allocate network block page.
            form = NetworkForm_network(request.POST)
            try:
                ip_type = form.data.get('ip_type')
                if ip_type not in ('4', '6'):
                    raise ValidationError("IP type must be either IPv4 or "
                            "IPv6.")
                network_str = form.data.get('network', '')
                try:
                    if ip_type == '4':
                        network = ipaddr.IPv4Network(network_str)
                    elif ip_type == '6':
                        network = ipaddr.IPv6Network(network_str)
                except ipaddr.AddressValueError, e:
                    raise ValidationError("Bad Ip address {0}".format(e))
                except ipaddr.NetmaskValueError, e:
                    raise ValidationError("Bad Netmask {0}".format(e))

                # Make sure this network doesn't exist.
                if ip_type == '4':
                    ip_upper, ip_lower = 0, int(network.network)
                else:
                    ip_upper, ip_lower = ipv6_to_longs(network.network)
                if (Network.objects.filter(ip_upper=ip_upper,
                        ip_lower=ip_lower).exists()):
                    raise ValidationError("This network has already been "
                            "allocated.")
            except ValidationError, e:
                form = NetworkForm_network(request.POST)
                if form._errors is None:
                    form._errors = ErrorDict()
                form._errors['__all__'] = ErrorList(e.messages)
                return render(request, 'network/network_form.html', {
                    'form': form,
                    'action': 'network'
                })


            request.session['net_wiz_vars'] = {'ip_type':ip_type,
                    'network_str':str(network)}
            parent = calc_parent_str(network_str, ip_type=ip_type)

            # Now build the form with the correct site.
            form = NetworkForm_site()
            if parent:
                form.fields['site'].initial = parent.site
            else:
                form = NetworkForm_site()

            return render(request, 'network/network_form.html', {
                'form': form,
                'action': 'site'
            })

        elif action == "site":
            # We are looking for the user to choose a site.
            form = NetworkForm_site(request.POST)
            try:
                site = form.data.get('site', False)
                if not site:
                    raise ValidationError("Please choose a site.")
                try:
                    site = Site.objects.get(pk=site)
                except ObjectDoesNotExist, e:
                    raise ValidationError("That site does not exist. Try again.")
            except ValidationError, e:
                form = NetworkForm_site(request.POST)
                if form._errors is None:
                    form._errors = ErrorDict()
                form._errors['__all__'] = ErrorList(e.messages)
                return render(request, 'network/network_form.html', {
                    'form': form,
                    'action': 'vlan'
                })
            nvars = request.session['net_wiz_vars']
            nvars['site_pk'] = site.pk
            request.session['net_wiz_state'] = site
            # Validation
            # return the choose or create vlan page.
            request.session['net_wiz_state'] = vlan
            form = NetworkForm_vlan()
            # return the allocate network block page.
            return render(request, 'network/network_form.html', {
                'form': form,
                'action': 'vlan',
            })

        elif action == "vlan":
            form = NetworkForm_vlan(request.POST)
            pdb.set_trace()
            try:
                form.is_valid()
                nvars = request.session['net_wiz_vars']
                if 'create_choice' not in form.data:
                    raise ValidationError("Select whether you are using an "
                            "exiting Vlan or if you are going to make a "
                            "new one.")
                create_choice = form.data['create_choice']
                if create_choice == 'new':
                    if 'name' not in form.data:
                        raise ValidationError("When creating a new Vlan, "
                                "please provide a vlan name")
                    if 'number' not in form.data:
                        raise ValidationError("When creating a new Vlan, "
                                "please provide a vlan number")
                    vlan_name = form.data['name']
                    vlan_number = form.data['number']
                    if not (vlan_name and vlan_number):
                        raise ValidationError("When creating a new Vlan, "
                                "please provide a string for the name and "
                                "an integer for the number.")
                    vlan = Vlan.objects.filter(name=vlan_name,
                                    number=vlan_number).exists()
                    if vlan:
                        raise ValidationError("The Vlan {0} {1} already "
                            "exists.".format(vlan_name, vlan_number))
                    else:
                         nvars['vlan_action'] = "new"
                         nvars['vlan_name'] = vlan_name
                         nvars['vlan_number'] = vlan_number
                elif create_choice == 'existing':
                    nvars['vlan_action'] = "existing"
                    vlan = form.data.get('vlan','')
                    try:
                        vlan = Vlan.objects.get(pk=vlan)
                    except ObjectDoesNotExist, e:
                        raise ValidationError("That Vlan does not exist. Try again.")
                    nvars['vlan_pk'] = vlan.pk
                    nvars['vlan_action'] = "existing"
                else:
                    nvars['vlan_action'] = "none"

            except ValidationError, e:
                form = NetworkForm_vlan(request.POST)
                if form._errors is None:
                    form._errors = ErrorDict()
                form._errors['__all__'] = ErrorList(e.messages)
                return render(request, 'network/network_form.html', {
                    'form': form,
                    'action': 'vlan'
                })
            # Validation
            # Return network detail view or fail.
            # Create objects and store to db.
            # Get rid of state var
            pdb.set_trace()
            site, network, vlan = create_objects(nvars)
            request.session['net_wiz_vars'] = nvars
            return render(request, 'network/wizard_confirm.html', {
                'site': site,
                'network': network,
                'vlan': vlan,
                'action': 'confirm',
            })
        elif action == "confirm":
            pdb.set_trace()
            nvars = request.session['net_wiz_vars']
            site, network, vlan = create_objects(nvars)
            if site:
                site.save()
            if vlan:
                vlan.save()
                network.vlan = vlan
            network.save()
            del request.session['net_wiz_vars']
            return redirect(network)

    # Catch everything else.
    # return the allocate network block page.
    form = NetworkForm_network()
    request.session['net_wiz_state'] = start
    # return the allocate network block page.
    return render(request, 'network/network_form.html', {
        'form': form,
        'action': 'network',
    })

def create_objects(nvars):
    # There needs to be major exception handling here. Things can go pretty
    # wrong.
    ip_type = nvars.get('ip_type', None)
    network_str = nvars.get('network_str', None)
    network = Network(network_str=network_str, ip_type=ip_type)
    network.update_network()

    site_pk = nvars.get('site_pk','')
    site = Site.objects.get(pk=site_pk)

    network.site = site

    if nvars.get('vlan_action', '') == "new":
        vlan_name = nvars.get('vlan_name', None)
        vlan_number = nvars.get('vlan_number', None)
        vlan = Vlan(name=vlan_name, number=vlan_number)
    elif nvars.get('vlan_action', '') == "existing":
        vlan_number = nvars.get('vlan_pk', '')
        vlan = Vlan.objects.get(pk=vlan_number)
    else:
        vlan = None

    network.vlan = vlan

    return site, network, vlan