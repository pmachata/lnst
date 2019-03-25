"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
idosch@mellanox.com (Ido Schimmel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

def linkneg(tl, if1, if2):
    if1_drv = str(if1.get_driver())
    if2_drv = str(if2.get_driver())

    # The mlx5_core upstream driver is currently buggy and does not support
    # link negotiation. Patches were sent to the NIC team.
    if 'mlx5' in if1_drv or 'mlx5' in if2_drv:
        return

    if 'mlx4' in if1_drv or 'mlx4' in if2_drv:
        speeds = [10000, 40000]
    else:
        speeds = [10000, 40000, 100000]

    for speed in speeds:
        tl.linkneg(if1, if2, True, speed=speed, timeout=30)
        tl.ping_simple(if1, if2)

def do_task(ctl, hosts, ifaces, aliases):
    m1_if1, sw_if1 = ifaces

    m1_if1.reset(ip=["192.168.101.10/24", "2002::1/64"])
    sw_if1.reset(ip=["192.168.101.11/24", "2002::2/64"])

    tl = TestLib(ctl, aliases)
    tl.wait_for_if(ifaces)
    linkneg(tl, sw_if1, m1_if1)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1")],
        ctl.get_aliases())
