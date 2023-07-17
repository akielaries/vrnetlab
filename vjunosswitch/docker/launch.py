#!/usr/bin/env python3

import datetime
import logging
import os
import re
import signal
import sys

import vrnetlab

def handle_SIGCHLD(signal, frame):
    os.waitpid(-1, os.WNOHANG)

def handle_SIGTERM(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, handle_SIGTERM)
signal.signal(signal.SIGTERM, handle_SIGTERM)
signal.signal(signal.SIGCHLD, handle_SIGCHLD)

TRACE_LEVEL_NUM = 9
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

def trace(self, message, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kws)
logging.Logger.trace = trace

class VJUNOSSWITCH_vm(vrnetlab.VM):
    def __init__(self, hostname, username, password, conn_mode):
        for e in os.listdir("/"):
            if re.search(".qcow2$", e):
                disk_image = "/" + e
        super(VJUNOSSWITCH_vm, self).__init__(username, password, disk_image=disk_image, ram=5120)
        self.qemu_args.extend(["-smp", "4,sockets=1,cores=4,threads=1"])
        # Additional CPU info
        self.qemu_args.extend([
            "-cpu", "IvyBridge,vme=on,ss=on,vmx=on,f16c=on,rdrand=on,hypervisor=on,arat=on,tsc-adjust=on,umip=on,arch-capabilities=on,pdpe1gb=on,skip-l1dfl-vmentry=on,pschange-mc-no=on,bmi1=off,avx2=off,bmi2=off,erms=off,invpcid=off,rdseed=off,adx=off,smap=off,xsaveopt=off,abm=off,svm=off"
            ])
        self.qemu_args.extend(["-overcommit", "mem-lock=off"])
        self.qemu_args.extend(["-display", "none", "-no-user-config", "-nodefaults", "-boot", "strict=on"])
        self.nic_type = "virtio-net-pci"
        self.num_nics = 11
        self.hostname = hostname
        self.smbios = ["type=1,product=VM-VEX"]
        self.qemu_args.extend(["-machine", "pc-i440fx-focal,usb=off,dump-guest-core=off,accel=kvm"])
        # extend QEMU args with device USB details
        self.qemu_args.extend(["-device", "piix3-usb-uhci,id=usb,bus=pci.0,addr=0x1.0x2"])
        self.conn_mode = conn_mode

    def bootstrap_spin(self):
        """ This function should be called periodically to do work.
        """

        # TODO: debug this, increased "spins" may be needed
        if self.spins > 300:
            # too many spins with no result ->  give up
            self.stop()
            self.start()
            return

        (ridx, match, res) = self.tn.expect([b"login:"], 1)
        if match: # got a match!
            if ridx == 0: # login
                self.logger.info("VM started")

                # Login
                self.wait_write("\r", None)
                self.wait_write("root", wait="login:")
                self.wait_write("", wait="root@:~ # ")
                self.logger.info("Login completed")

                # TODO some of bootstrap_config should be ran in here first. 
                # login, then execute basic init config items
                # run main config!
                #self.bootstrap_config()
                # close telnet connection
                self.tn.close()
                # startup time?
                startup_time = datetime.datetime.now() - self.start_time
                self.logger.info("Startup complete in: %s" % startup_time)
                # mark as running
                self.running = True
                return

        # no match, if we saw some output from the router it's probably
        # booting, so let's give it some more time
        if res != b'':
            self.logger.trace("OUTPUT: %s" % res.decode())
            # reset spins if we saw some output
            self.spins = 0

        self.spins += 1

        return

    def config(self):
        pass

    def bootstrap_config(self):
        """ Do the actual bootstrap config using send and wait
        """#TODO: look into passing in config to actual image instead
        # PASS .conf directly to /config/juniper.conf?? TODO
        self.logger.info("applying bootstrap configuration")
        self.wait_write("cli", "#") 
        self.wait_write("set cli screen-length 0", ">")
        self.wait_write("set cli screen-width 511", ">")
        self.wait_write("set cli complete-on-space off", ">")
        self.wait_write("configure", ">")
        self.wait_write("top delete", "#")
        self.wait_write("yes", "Delete everything under this level? [yes,no] (no) ")
        self.wait_write("set system login user %s class super-user authentication plain-text-password" % ( self.username ), "#")
        self.wait_write(self.password, "New password:")
        self.wait_write(self.password, "Retype new password:")
        self.wait_write("set system root-authentication plain-text-password", "#")
        self.wait_write(self.password, "New password:")
        self.wait_write(self.password, "Retype new password:")
        self.wait_write("delete chassis auto-image-upgrade")
        self.wait_write("commit")
        #self.wait_write("set system services ssh", "#")
        #self.wait_write("set system services netconf ssh", "#")
        # remove DHCP6 configuration before setting DHCP4
        self.wait_write("delete interfaces fxp0 unit 0 family inet6")
        # set interface fxp0  on dedicated management vrf, to avoid 
        # 10.0.0.0/24 to overlap with any "testing" network
        self.wait_write("set interfaces fxp0 unit 0 family inet address 10.0.0.15/24", "#")
        self.wait_write("set system management-instance", "#")
        self.wait_write("set routing-instances mgmt_junos description management-instance", "#")
        # allow NATed outgoing traffic (set the default route on the management vrf)
        self.wait_write("set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop 10.0.0.2", "#")
        self.wait_write("commit")
        self.wait_write("exit")
        # write another exist as sometimes the first exit from exclusive edit abrupts before command finishes
        self.wait_write("exit", wait=">")
        self.logger.info("completed bootstrap configuration")

    def startup_config(self):
        """Load additional config provided by user."""

        if not os.path.exists(STARTUP_CONFIG_FILE):
            self.logger.trace(f"Startup config file {STARTUP_CONFIG_FILE} is not found")
            return

        self.logger.trace(f"Startup config file {STARTUP_CONFIG_FILE} exists")
        with open(STARTUP_CONFIG_FILE) as file:
            config_lines = file.readlines()
            config_lines = [line.rstrip() for line in config_lines]
            self.logger.trace(f"Parsed startup config file {STARTUP_CONFIG_FILE}")

        self.logger.info(f"Writing lines from {STARTUP_CONFIG_FILE}")

        self.wait_write("cli", "#", 10)
        self.wait_write("configure", ">", 10)
        # Apply lines from file
        for line in config_lines:
            self.wait_write(line)
        # Commit and GTFO
        self.wait_write("commit")
        self.wait_write("exit")


class VJUNOSSWITCH(vrnetlab.VR):
    def __init__(self, hostname, username, password, conn_mode):
        super(VJUNOSSWITCH, self).__init__(username, password)
        self.vms = [ VJUNOSSWITCH_vm(hostname, username, password, conn_mode) ]

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--trace", action="store_true", help="enable trace level logging")
    parser.add_argument("--hostname", default="vr-vjunosswitch", help="vJunos-switch hostname")
    parser.add_argument("--username", default="vrnetlab", help="Username")
    parser.add_argument("--password", default="VR-netlab9", help="Password")
    parser.add_argument("--connection-mode", default="tc", help="Connection mode to use in the datapath")
    args = parser.parse_args()


    LOG_FORMAT = "%(asctime)s: %(module)-10s %(levelname)-8s %(message)s"
    logging.basicConfig(format=LOG_FORMAT)
    logger = logging.getLogger()

    logger.setLevel(logging.DEBUG)
    if args.trace:
        logger.setLevel(1)

    vr = VJUNOSSWITCH(args.hostname,
        args.username,
        args.password,
        conn_mode=args.connection_mode,
    )
    vr.start()
