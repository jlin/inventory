def get_networks(site):
    return site.network_set.filter(site=site)


def get_vlans(site):
    """
    v(S^i) = {N^i^v | N^i e n(S^i)}
    returns a set
    """
    vlans = set()
    for network in site.network_set.all():
        vlans.add(network.vlan)
    return vlans
