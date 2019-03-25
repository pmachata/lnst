"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
nogahf@mellanox.com (Nogah Frankel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

def test_ip(major, minor):
    return ["192.168.10%d.%d/24" % (major, minor),
            "2002:%d::%d/64" % (major, minor)]

def mcgrp(i):
    return "239.255.1.%d" % i

def test_standard_multicast(tl, sender, listeners, group, sw_br,
                            peers):
    for l in listeners:
            sw_br.add_br_mdb(str(peers[l].get_devname()), group)

    bridged = peers.keys()
    bridged.remove(sender)
    res = tl.iperf_mc(sender,  bridged, group)
    expected = [i in listeners for i in bridged]
    tl.mc_ipref_compare_result(bridged, res, expected)

    for l in listeners:
        sw_br.del_br_mdb(str(peers[l].get_devname()), group)

    res = tl.iperf_mc(sender,  bridged, group)
    expected = [False for i in bridged]
    tl.mc_ipref_compare_result(bridged, res, expected)

def do_task(ctl, hosts, ifaces, bridges, aliases):
    m1, m2, sw = hosts
    m1_if, m2_if, m3_if, m4_if, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces
    peers = {m1_if: sw_if1, m2_if: sw_if2, m3_if: sw_if3, m4_if: sw_if4}

    for bridge in bridges:
        bridge.set_br_mcast_snooping(False)

    # Create a bridge
    sw_ports = peers.values()
    sw_br = sw.create_bridge(slaves=sw_ports, options={"vlan_filtering": 1,
                                                       "multicast_querier": 1})

    m1_if.set_addresses(test_ip(1,1))
    m2_if.set_addresses(test_ip(1,2))
    m3_if.set_addresses(test_ip(1,3))
    m4_if.set_addresses(test_ip(1,4))

    tl = TestLib(ctl, aliases)
    tl.wait_for_if(ifaces)
    tl.check_cpu_traffic(sw_ports, test=False)
    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.enable_multicast()

    test_standard_multicast(tl, m1_if, [m2_if, m4_if], mcgrp(3), sw_br, peers)
    test_standard_multicast(tl, m1_if, [m4_if], mcgrp(4), sw_br, peers)
    test_standard_multicast(tl, m2_if, [m1_if, m2_if, m4_if], mcgrp(5), sw_br, peers)

    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.disable_multicast()
    tl.check_cpu_traffic(sw_ports)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("veth1"),
         ctl.get_host("machine1").get_interface("veth3"),
         ctl.get_host("machine2").get_interface("veth1"),
         ctl.get_host("machine2").get_interface("veth3"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
        [ctl.get_host("machine1").get_interface("brif1"),
         ctl.get_host("machine1").get_interface("brif2"),
         ctl.get_host("machine2").get_interface("brif1"),
         ctl.get_host("machine2").get_interface("brif2")],
        ctl.get_aliases())
