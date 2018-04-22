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
from random import randint
from time import sleep
from RedTestLib import RedTestLib
from PrioTestLib import PrioTestLib
import logging

def test_ip(major, minor, prefix=24):
    return "192.168.10%d.%d%s" % (major, minor,
    "/" + str(prefix) if prefix > 0 else "")

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    tl = TestLib(ctl, aliases)
    prio_test = PrioTestLib(tl, sw, {sw_if1: m1_if1, sw_if2: m2_if1})
    prio_test.create_bottleneck(aliases)
    prio_test.set_prio(bands=3, priomap="1 1 1 1 1 0 0 0 0")
    sleep(30)


    logging.info("Start traffic in band 0")
    prio_test.send_bg_traffic(6)
    sleep(30)

    logging.info("Send traffic in band 1 (shouldn't pass)")
    prio_test.check_traffic_passes(0, False)

    logging.info("Remap background traffic to band 6")
    prio_test.set_prio(bands=7, priomap="1 1 1 1 6 6 6 6")
    sleep(30)
    logging.info("Send traffic in band 1 (should pass)")
    prio_test.check_traffic_passes(0, True)

    logging.info("Remap background traffic to band 0")
    prio_test.set_prio(bands=3, priomap="1 1 1 1 0 0 0 0")
    sleep(30)
    logging.info("Send traffic in band 1 (shouldn't pass)")
    prio_test.check_traffic_passes(0, False)
    prio_test.stop_bg_traffic()

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
