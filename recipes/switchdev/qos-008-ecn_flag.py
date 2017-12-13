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
import logging
from RedTestLib import RedTestLib

def run_actual_test(red_test):
    red_test.set_red(1300000, 1300001, ecn=True)

    red_test.set_traffic_ecn_disable()
    # ecn acts as red
    low_red_res = red_test.tune_low_rate(0.9)
    red_test.check_red_low(low_red_res)

    high_red_res = red_test.tune_high_rate(0.9)
    red_test.check_red_high(high_red_res)

    red_test.set_traffic_ecn_enable()
    # ecn no longer acts as red
    low_ecn_res = red_test.tune_low_rate(0.95)
    red_test.check_ecn_low(low_ecn_res)

    high_ecn_res = red_test.tune_high_rate(1.01)
    red_test.check_ecn_high(high_ecn_res)

    red_test.set_higher_rate()
    red_test.set_higher_rate()
    very_high_ecn_res = red_test.send_traffic()
    red_test.check_ecn_very_high(very_high_ecn_res, high_ecn_res)

    red_test.set_no_red()
    red_test.check_no_ecn()

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.reset(ip=["192.168.101.10/24", "2002::1/64"])
    m2_if1.reset(ip=["192.168.101.11/24", "2002::2/64"])

    tl = TestLib(ctl, aliases)
    red_test = RedTestLib(tl, sw, {sw_if1:m1_if1, sw_if2:m2_if1})
    red_test.create_bottleneck(aliases)
    sleep(30)
    try:
        run_actual_test(red_test)
    except Exception as e:
        logging.error("Test run failed")
        tl.custom(sw, "RED-ECN TOS flag test", "Failed because of %s" % e)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
