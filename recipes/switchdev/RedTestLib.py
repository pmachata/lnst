"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
nogahf@mellanox.com (Nogah Frankel)
"""

from time import sleep
import logging
from lnst.Controller.Task import ctl

# Merely a container for a run results
# Holds:
#   stats: The last red stats taken in the run, or, for none red runs, some
#   minimal data from the normal stats.
#   backlogs: A list of the backlogs sizes during the runs. Filtered so a
#   backlog won't be counted if there was no TX in the time it was taken.
class RedTestResults:
    def __init__(self, red_stats, backlogs):
        self.stats = red_stats
        self.backlogs = backlogs

    def check_stats_minimal(self, log_function):
        if self.stats == {}:
            log_function("Stats collection failed")
            raise Exception("No stats")

    def compare_stats(self, drops, tx_packets, threshold):
        err = []
        if abs(drops - self.stats["drops"]) > threshold:
            err.append("RED stats's drops %d != actual drops %d" %
                       (self.stats["drops"], drops))
        if abs(tx_packets - self.stats["tx_packets"]) > threshold:
            err.append("RED stats's tx packets %d != actual number %d" %
                       (self.stats["tx_packets"], tx_packets))
        if abs(self.stats["early"] + self.stats["pdrop"]-
               self.stats["drops"]) > threshold:
            err.append("%d early drops + %d pdrops != total drops %d" %
                       (self.stats["early"], self.stats["pdrop"],
                        self.stats["drops"]))
        return err

class RedTestLib:
    def __init__(self, tl, switch, links):
        self.tl = tl
        self.switch = switch
        self.links = links
        self.ports = links.keys()
        self.switch.create_bridge(slaves=self.ports,
                                  options={"vlan_filtering": 1})
        self.rate = 0
        self.threshold = 100
        self.speed_base = 1000
        self.min = 0
        self.max = 0
        self.rate = self.speed_base
        self.set_traffic_ecn_enable()

    # To be used to report about problem that shouldn't occur.
    def generic_error_function(self, msg):
        self.tl.custom(self.switch, "TC qdisc RED", msg)

    # To be used for checks that always needs to report passing or failing
    def test_result(self, desc, msg):
        self.tl.custom(self.switch, desc, msg)

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
        stats = self.egress_port.qdisc_red_stats()
        self.check_stats_were_offloaded(stats)
        self.min = min
        self.max = max

    def set_no_red(self):
        self.min = 0
        self.max = 0
        self.egress_port.unset_qdisc_red()

    def set_low_rate(self):
        self.rate = self.speed_base * 0.99
        logging.info("Set slow rate %d M" % self.rate)

    def set_lower_rate(self):
        self.rate *= 0.9
        logging.info("New rate is %d M" % self.rate)

    def set_high_rate(self):
        self.rate = max(self.speed_base * 1.01, self.rate * 1.25)
        logging.info("Set high rate %d M" % self.rate)

    def set_higher_rate(self):
        self.rate *= 1.1
        logging.info("New rate is %d M" % self.rate)

    def check_stats_were_offloaded(self, stats):
        if stats == {}:
            self.generic_error_function("Config failed")
            raise Exception("test failed")
        if not stats["offload"]:
            self.generic_error_function("Offloading failed")
            raise Exception("test failed")

    # Send traffic in the set rate.
    # If RED is set, collect res stats while the traffic is being sent.
    # Collect the backlog size for every time there is a traffic passing via the
    # red qdisc, indicated by change in the TX counter.
    def send_traffic(self, is_red = True):
        rx_before = self.ingress_port.link_stats()["rx_packets"]
        tx_before = self.egress_port.link_stats()["tx_packets"]
        pkt_size = self.links[self.ingress_port].get_mtu()

        if is_red: # if RED is enabled
            self.egress_port.collect_qdisc_red_stats()

        self.tl.pktgen(self.links[self.ingress_port],
                       self.links[self.egress_port], pkt_size, count=10**6,
                       rate=str(self.rate)+"M", tos=self.tos)
        sleep(3)

        rx_after = self.ingress_port.link_stats()["rx_packets"]
        tx_after = self.egress_port.link_stats()["tx_packets"]
        tx_packets = tx_after - tx_before
        rx_packets = rx_after - rx_before
        drops = rx_packets - tx_packets

        if is_red:
            backlog, stats = self.egress_port.stop_collecting_qdisc_red_stats()
            self.check_stats_were_offloaded(stats)
            results = RedTestResults(stats, backlog)
            results.check_stats_minimal(self.generic_error_function)
            errors = results.compare_stats(drops, tx_packets, self.threshold)
            for err_msg in errors:
                self.generic_error_function(err_msg)
        else:
            stats = {"drops": drops, "tx_packets": tx_packets}
            results = RedTestResults(stats, [])

        logging.info("Sent %d packets, dropped %d packets" % (tx_after, drops))
        return results

    # Send traffic and check the backlogs stats later. If the max backlog is
    # over some threshold (given as a ratio to the min red limit), lower the
    # rate and re-run.
    def tune_low_rate(self, backlog_threshold):
        full_backlog_size = self.min * backlog_threshold
        logging.info("Tune low rate till max backlog is below %s of the "
                     "backlog (%d bytes)" % (backlog_threshold,
                                             full_backlog_size))
        self.set_low_rate()
        while True:
            res = self.send_traffic()
            if max(res.backlogs) <= full_backlog_size:
                return res
            logging.info("The max backlog was %d bytes. Decrease rate" %
                          max(res.backlogs))
            self.set_lower_rate()

    # Send traffic and check the backlogs stats later. If most of the backlogs
    # were less than the given threshold (given as a ratio to the min red
    # limit), set the rate to higher.
    def tune_high_rate(self, backlog_threshold):
        full_backlog_size = self.min * backlog_threshold
        logging.info("Tune high rate till more than half of the backlogs are "
                     "above below %s of the backlog (%d bytes)" %
                     (backlog_threshold, full_backlog_size))
        self.set_high_rate()
        while True:
            res = self.send_traffic()
            backlogs_overlimit = len([b for b in res.backlogs
                                      if b > full_backlog_size])
            if backlogs_overlimit >= 0.5 * len(res.backlogs):
               return res
            logging.info("Only %d backlogs (from %f total) were over the "
                         "limit. Increase rate" %
                         (backlogs_overlimit, len(res.backlogs)))
            self.set_higher_rate()

    # Check that there were no pdrops (with some error margins of the internal
    # threshold)
    def check_no_pdrops(self, desc, res):
        msg = ""
        if res.stats["pdrop"] > self.threshold:
            msg = "Too many pdrops (%d)" % res.stats["pdrop"]
        self.test_result(desc, msg)

    # Check the run res for red with or without ecn for low rate traffic.
    def check_red_ecn_low(self, name, res):
        logging.info("Low rate %s, expect no drops nor marks" % name)

        desc = "%s marking low rate" % name
        msg = ""
        if res.stats["marked"] > self.threshold:
            msg = "marked %d packets when expected 0" % res.stats["marked"]
        self.test_result(desc, msg)

        desc = "%s low rate" % name
        msg = ""
        if res.stats["early"] > self.threshold:
            msg = "Too many packets were dropped (%d)" % res.stats["early"]
        self.test_result(desc, msg)

        self.check_no_pdrops("%s low rate - pdrops" % name, res)

    def check_red_low(self, res):
        self.check_red_ecn_low("RED", res)

    def check_ecn_low(self, res):
        self.check_red_ecn_low("ECN", res)

    # Check the run res for red for high rate traffic.
    def check_red_high(self, res):
        logging.info("High rate RED, expect early drops but no pdrops and "
                     "worse throughput than in low rate")

        full_backlog_size = self.min * 0.95
        backlogs_overlimit = len([b for b in res.backlogs
                                  if b > full_backlog_size])
        desc = "RED high rate - early drops"
        msg = ""
        if res.stats["early"] < self.threshold * backlogs_overlimit:
            msg = "Not enough early drops (%d)" % res.stats["early"]
        self.test_result(desc, msg)

        self.check_no_pdrops("RED high rate - pdrops", res)

        desc = "RED high rate - throughput"
        msg = ""
        if self.min > res.stats["tx_bytes"]:
            msg = "throughput %d is lower than the minimal limit %d" % \
                   (res.stats["tx_packets"], self.min)
        self.test_result(desc, msg)

    # Check the run res for high rate traffic and no res. Compare them to the
    # results in the same rate with red.
    def check_no_red(self, res, high_red_res):
        logging.info("No RED test, expect no worse drops and throughput than "
                     "with RED")
        desc = "no RED - drops"
        msg = ""
        if res.stats["drops"] > high_red_res.stats["drops"]:
            msg = "more drops (%d) than with RED (%d)" % \
                   (res.stats["drops"], high_red_res.stats["drops"])
        self.test_result(desc, msg)

        desc = "no RED - throughput"
        msg = ""
        if high_red_res.stats["tx_packets"] > res.stats["tx_packets"]:
            msg = "throughput %d is lower than with RED %d" % \
                  (res.stats["tx_packets"], high_red_res.stats["tx_packets"])
        self.test_result(desc, msg)

    # Check the run res for red-ecn for high rate traffic.
    def check_ecn_high(self, res):
        logging.info("High rate ECN, expect marks, allow pdrops but not "
                     "early drops")

        # we expect at least all the packets over the limit to be marked
        should_mark = sum(max(0, x - self.max) for x in res.backlogs)
        pkt_size = int(self.links[self.ingress_port].get_mtu())
        should_mark /= pkt_size

        should_not_mark = sum(x for x in res.backlogs if x < self.min)
        should_not_mark /= pkt_size

        desc = "ECN marking high rate"
        msg = ""
        if res.stats["marked"] < should_mark - self.threshold:
            msg = "marked %d packets when expected at least %d" % \
                (res.stats["marked"], should_mark)
        elif res.stats["marked"] > res.stats["tx_packets"] - should_not_mark:
            msg = "marked %d packets when expected no more than %d" % \
                  (res.stats["marked"],
                   res.stats["tx_packets"] - should_not_mark)
        self.test_result(desc, msg)

        desc = "ECN early drops - high rate"
        msg = ""
        if res.stats["early"] > self.threshold:
            msg = "Too many packets were early dropped %d (expected none)" % \
                  res.stats["early"]
        self.test_result(desc, msg)

    # Compare the run res of red-ecn with very high traffic rate to the ones
    # with lower (but still high) rate.
    def check_ecn_very_high(self, res, high_ecn_res):
        logging.info("Very high rate ECN, expect lots of pdrops")
        desc = "ECN marking - pdrops"
        msg = ""
        if res.stats["pdrop"] * 0.9 < high_ecn_res.stats["pdrop"]:
            msg = "only %d packets got pdrops, expected >> %d" % \
                  (res.stats["pdrop"], high_ecn_res.stats["pdrop"])
        self.test_result(desc, msg)

    # Run traffic and see that it doesn't get marked.
    def check_no_ecn(self):
        logging.info("No ECN check: run traffic and see check on the "
                     "receiving host that it was not marked")
        receiving_port = self.links[self.egress_port]
        host = receiving_port.get_host()
        host.sync_resources(modules=["PacketAssert"])
        options = {"min":0, "max" :0, "promiscuous" :True,
                   "filter" :'ip[1]&3=3',
                   "interface": receiving_port.get_devname()}
        packet_assert_mod = ctl.get_module("PacketAssert", options=options)
        proc = host.run(packet_assert_mod, bg=True)
        pkt_size = self.links[self.ingress_port].get_mtu()
        self.tl.pktgen(self.links[self.ingress_port],
                       self.links[self.egress_port], pkt_size, count=10**6,
                       tos=self.tos, rate=str(self.rate)+"M")
        proc.intr()

