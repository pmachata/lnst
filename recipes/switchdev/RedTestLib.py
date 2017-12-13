"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
nogahf@mellanox.com (Nogah Frankel)
"""

import logging

class RedTestLib:
    def __init__(self, tl, switch, links):
        self.tl = tl
        self.switch = switch
        self.links = links
        self.ports = links.keys()
        self.switch.create_bridge(slaves=self.ports,
                                  options={"vlan_filtering": 1})
        self.rate = 0
        self.desc = "TC qdisc RED"
        self.threshold = 100
        self.speed_base = 1000
        self.min = 0
        self.max = 0
        self.rate = self.speed_base
        self.set_traffic_ecn_enable()

    # choose egress & ingress ports and set their speed to create bottleneck
    def create_bottleneck(self, aliases):
        self.egress_port = self.ports[0]
        self.ingress_port = self.ports[1]
        self.egress_port.set_speed(self.speed_base)
        self.ingress_port.set_speed(aliases["speed_hi"])

    def set_traffic_ecn_enable(self):
        self.tos = '01'
        logging.info("traffic will be ecn enabled")

    def set_traffic_ecn_disable(self):
        self.tos = '00'
        logging.info("traffic will be ecn disabled")

    def set_red(self, min, max, prob=None, ecn=False):
        limit = max * 4
        avpkt = 1000
        self.egress_port.set_qdisc_red(limit, avpkt, min, max, ecn=ecn)
        self.min = min
        self.max = max

    def set_no_red(self):
        self.min = 0
        self.max = 0
        self.egress_port.unset_qdisc_red()

