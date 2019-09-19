import logging
import tempfile
from time import sleep
from collections import OrderedDict

MAX_OFFSET = 75
SLEEP_TIME = 60
NUMBER_OF_CHECKS = 60
# Accept 10% of wrong samples
ACCEPTED_WRONG_SAMPLES = 6
CLOCK_CHANGE = 600

class Machine(object):
    def __init__(self, machine, machine_name, ifaces, desired_hops):
        self.machine = machine
        self.machine_name = machine_name
        self.ifaces = ifaces
        self.desired_hops = desired_hops
        self.cfg = {}

    def get_machine(self):
        return self.machine

    def get_machine_name(self):
        return self.machine_name

    def get_ifaces(self):
        return self.ifaces

    def get_desired_hops(self):
        return self.desired_hops

    def get_cfg(self):
        return self.cfg

    def get_uds_address(self):
        return "/var/run/ptp4l-%s" % self.machine_name

    def set_opt(self, section, option=None, value=None):
        sec = self.cfg.setdefault(section, {})
        if option is not None:
            sec[option] = value

    def sysctl_set(self):
        self.sysctl_orig = {}
        output = self.machine.run("sysctl -ar '\\brp_filter'")
        for line in output.out().split('\n'):
            fields = line.split(" = ")
            if len(fields) > 1:
                key, value = fields
                self.sysctl_orig[key] = value
                self.machine.run("sysctl -w %s=0" % key)

    def sysctl_restore(self):
            for key, value in self.sysctl_orig.items():
                self.machine.run("sysctl -w %s=%s" % (key, value))

    def is_supported_speed(self, speed):
        for iface in self.ifaces:
            output = self.machine.run("ethtool %s" % iface.get_devname())
            supported_speeds = output.out()[output.out().find("Supported link modes"):]
            supported_speeds = supported_speeds[:supported_speeds.find("Advertised link modes")]
            speed += 'base'
            if speed not in supported_speeds:
                return False
        return True


    def configure(self, transport):
        self.cfg = OrderedDict()
        self.set_opt("global", "logSyncInterval", "0")
        self.set_opt("global", "step_threshold", "1.0")
        self.set_opt("global", "network_transport", transport)
        self.set_opt("global", "tx_timestamp_timeout", "10")
        self.set_opt("global", "summary_interval", "2")
        self.set_opt("global", "logSyncInterval", "-2")
        self.set_opt("global", "logMinDelayReqInterval", "-2")
        self.set_opt("global", "uds_address", self.get_uds_address())
        self.set_opt("global", "userDescription", self.machine_name)

class Master(Machine):
    def configure(self, transport):
        Machine.configure(self, transport)
        Machine.set_opt(self, "global", "priority1", "126")

class SLAVE2(Machine):
    # SLAVE1 and SLAVE2 run on the same machine (m1).
    # Do not have to handle sysctl twice.
    def sysctl_set(self):
        pass

    def sysctl_restore(self):
        pass

class PortSpeed(object):
    def __init__(self, machines, speed):
        self._machines = machines
        self._speed = speed

    def set_speed(self, command):
        for machine_obj in self._machines.values():
            m = machine_obj.get_machine()
            for iface in machine_obj.get_ifaces():
                m.run("ethtool -s %s %s" % (iface.get_devname(), command))

    def __enter__(self):
        self.set_speed("speed %s autoneg off" % self._speed)

    def __exit__(self, exc_type, exc_value, traceback):
        self.set_speed("autoneg on")

class LargeDrift(object):
    def __init__(self, machines):
        self._machines = machines

    def __enter__(self):
        m = self._machines['MASTER'].get_machine()
        iface = (self._machines['MASTER'].get_ifaces())[0]
        m.run("phc_ctl %s adj %d" % (iface.get_devname(), CLOCK_CHANGE))

    def __exit__(self, exc_type, exc_value, traceback):
        # Have to reset all clocks and not only master clock because all
        # of them were synchronized with master clock after ptp running.
        for machine_obj in self._machines.values():
            m = machine_obj.get_machine()
            ifaces = machine_obj.get_ifaces()

            for iface in ifaces:
                m.run("phc_ctl %s set" % iface.get_devname())

class PtpTest(object):
    def __init__(self, tl, hosts, ifaces):
        self.tl = tl
        self.m1, self.m2, self.sw = hosts
        m1_if1, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3 = ifaces

        self.machines = { 'MASTER': Master(self.m1, 'MASTER', [m1_if1],
                                        desired_hops=0),
                          'BC' : Machine(self.sw,'BC', [sw_if1,
                                         sw_if2, sw_if3], desired_hops=1),
                          'SLAVE1': Machine(self.m2, 'SLAVE1', [m2_if1],
                                        desired_hops=2),
                          'SLAVE2': SLAVE2(self.m2, 'SLAVE2', [m2_if2],
                                        desired_hops=2)
                        }

    def write_ini(self, machine_name):
        cfg = self.machines[machine_name].get_cfg()
        with tempfile.NamedTemporaryFile(prefix="ini-", dir="/tmp") as inifile:
            for sect, opts in cfg.items():
                inifile.write("[%s]\n" % sect)
                for opt, val in opts.items():
                    inifile.write("%s %s\n" % (opt, val))
                inifile.write("\n")

            inifile.flush()

            m = self.machines[machine_name].get_machine()
            remote_file = m.copy_file_to_machine(local_path=inifile.name)

        return remote_file

    def run_ptp4l(self):
        cleanup = []
        for machine_obj in self.machines.values():
            interfaces = machine_obj.get_ifaces()

            m = machine_obj.get_machine()
            for iface in interfaces:
                machine_obj.set_opt(iface.get_devname())
            remote_file = self.write_ini(machine_obj.get_machine_name())
            ptp_proccess = m.run("ptp4l -f %s -H -m" % remote_file, bg=True)
            cleanup.append([machine_obj, remote_file, ptp_proccess])
        return cleanup

    def init_setup(self, transport):
        for machine_obj in self.machines.values():
            machine_obj.configure(transport)

    def get_param_value(self, cmd_out, param):
        for line in cmd_out.out().split('\n\t'):
            fields = line.split()
            # if param is the first word in this line,
            # return the value of this param.
            if len(fields) > 0 and fields[0] == param:
                key, value = fields
                return value
        raise RuntimeError("%s not found in pmc output" % param)

    def check_offset(self, machine, uds_address):
        output = machine.run("pmc -u -b 0 -s %s 'GET TIME_STATUS_NP'" % \
                            uds_address)
        offset = self.get_param_value(cmd_out=output, param='master_offset')
        offset = abs(int(offset))

        if offset >= MAX_OFFSET:
            return 1
        return 0

    def check_wrong_samples(self, err_msg):
        wrong1 = wrong2 = 0

        m1 = self.machines['SLAVE1'].get_machine()
        m2 = self.machines['SLAVE2'].get_machine()

        uds1 = self.machines['SLAVE1'].get_uds_address()
        uds2 = self.machines['SLAVE2'].get_uds_address()

        for i in range(NUMBER_OF_CHECKS):
            wrong1 += self.check_offset(m1, uds1)
            wrong2 += self.check_offset(m2, uds2)

            sleep(1)

        for machine_name, wrong in [('SLAVE1', wrong1), ('SLAVE2', wrong2)]:
            if wrong > ACCEPTED_WRONG_SAMPLES:
                err_msg.append("Got %d/%d wrong samples in %s" % \
                        (wrong, NUMBER_OF_CHECKS, machine_name))

    def check_hops(self, err_msg):
        for machine_obj in self.machines.values():
            m = machine_obj.get_machine()
            uds_address = machine_obj.get_uds_address()
            desired_hops = machine_obj.get_desired_hops()
            machine_name = machine_obj.get_machine_name()

            output = m.run("pmc -u -b 0 -s %s 'GET CURRENT_DATA_SET'" % \
                        uds_address)
            hops = self.get_param_value(cmd_out=output, param='stepsRemoved')

            if not int(hops) == desired_hops:
                err_msg.append("%s is %s steps removed from master, expected" \
                        " %d" % (machine_name, hops, desired_hops))

    def run_test(self, transport, desc, extra_sleep=False):
        self.init_setup(transport)
        cleanup = self.run_ptp4l()

        logging.info("sleep %s sec" % SLEEP_TIME)
        sleep(SLEEP_TIME)

        if extra_sleep:
            logging.info("Extra sleep, more %d sec" % (2*SLEEP_TIME))
            sleep(2*SLEEP_TIME)

        err_msg = []
        self.check_wrong_samples(err_msg)

        self.check_hops(err_msg)

        self.tl.custom(self.sw, "ptp: %s" % desc, "\n".join(err_msg))

        for machine_obj, inifile, proccess in cleanup:
            machine_obj.get_machine().run("rm -f %s" % inifile)
            proccess.kill()

    def get_speeds(self):
        speeds = [1000, 10000]
        for machine_obj in self.machines.values():
            if not machine_obj.is_supported_speed('100000'):
                return speeds

        speeds.append(100000)
        return speeds

    def run_tests(self):
        for machine_obj in self.machines.values():
            machine_obj.sysctl_set()

        # In the first time it takes for clocks more time be locked.
        self.run_test(transport="UDPv6", desc="IPv6", extra_sleep=True)
        self.run_test(transport="L2", desc="IEEE-802.3")

        sppeds = self.get_speeds()
        for speed in sppeds:
            with PortSpeed(self.machines, speed):
                self.run_test(transport="UDPv4", desc="port speed = %s"
                        % speed)

        with LargeDrift(self.machines):
            self.run_test(transport="UDPv4", desc="Large drift test")

        for machine_obj in self.machines.values():
            machine_obj.sysctl_restore()
