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
import logging

def run_actual_test(red_test):
    red_test.set_red(1500000, 1500001)

    low_red_res = red_test.tune_low_rate(backlog_threshold = 0.9)
    red_test.check_red_low(low_red_res)

    high_red_res = red_test.tune_high_rate(backlog_threshold = 0.9)
    red_test.check_red_high(high_red_res)

    red_test.set_no_red()
    no_red_res = red_test.send_traffic(is_red = False)
    red_test.check_no_red(no_red_res, high_red_res)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    tl = TestLib(ctl, aliases)
    red_test = RedTestLib(tl, sw, {sw_if1:m1_if1, sw_if2:m2_if1})
    red_test.create_bottleneck(aliases)
    if ctl.get_alias("use_prio_as_root"):
        red_test.set_prio()
    sleep(30)

    try:
        run_actual_test(red_test)
    except Exception as e:
        logging.error("Test run failed")
        tl.custom(sw, "Basic RED test", "Failed because of %s" % e)


do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
