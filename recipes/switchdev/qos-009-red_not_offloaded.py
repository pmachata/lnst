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
import logging

def do_task(ctl, hosts, native_ifaces, construct_ifaces, aliases):
    m1, m2, sw = hosts
    tl = TestLib(ctl, aliases)
    for iface in construct_ifaces:
        desc = "RED setting on %s without offloading" % iface.get_devname()
        msg = ""
        iface.set_qdisc_red(10**6, 10**3, 3*10**3, 3*10**4)
        red_stats = iface.qdisc_red_stats()
        if red_stats == {}:
            msg = "Setting RED on %s failed" % iface.get_devname()
        elif red_stats["offload"]:
            msg = "RED on %s appears as offloaded" % iface.get_devname()
        tl.custom(sw, desc, msg)

    for iface in native_ifaces:
        desc = "RED setting on %s with offloading" % iface.get_devname()
        msg = ""
        iface.set_qdisc_red(10**6, 10**3, 3*10**3, 3*10**4)
        red_stats = iface.qdisc_red_stats()
        if red_stats == {}:
            msg = "Setting RED on %s failed" % iface.get_devname()
        elif not red_stats["offload"]:
            msg = "RED on %s appears as offloaded" % iface.get_devname()
        tl.custom(sw, desc, msg)

    if1 = native_ifaces[0]
    desc = "RED setting with too high max (%d)" % (5*10**7)
    msg = ""
    iface.set_qdisc_red(10**8, 10**3, 10**7, 5*10**7, change = True,
                        burst = 10**4)
    red_stats = iface.qdisc_red_stats()
    if red_stats == {}:
        msg = "Setting RED on %s with very high max failed" % \
              iface.get_devname()
    elif red_stats["offload"]:
         msg = "RED on %s appears as offloaded even though max is not " \
               "possible" % iface.get_devname()
    tl.custom(sw, desc, msg)

    desc = "RED re-setting with legal max"
    msg = ""
    iface.set_qdisc_red(10**7, 10**3, 2*10**6, 3*10**6, change = True,
                        burst = 2*10**3)
    red_stats = iface.qdisc_red_stats()
    if red_stats == {}:
        msg = "Setting RED on %s with legal max failed" % iface.get_devname()
    elif not red_stats["offload"]:
         msg = "RED on %s appears as not offloaded even though max is legal" % \
               iface.get_devname()
    tl.custom(sw, desc, msg)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
         [ctl.get_host("switch").get_interface("bond1"),
         ctl.get_host("switch").get_interface("br1"),
         ctl.get_host("switch").get_interface("if4.10")],
        ctl.get_aliases())
