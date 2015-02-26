"""
A MachineDetector is used to find 'probable' machines that are connected
to a computer, primarly by USB connection. It can detect multiple machines
by passing multiple machine names.

Currently machines are detected by VID/PID (vendorID/productID) of
connected USB devices, although this can be extended in the future.

This may require MakerBot's version of pyserial to use features to tie a
serial device to it's USB VID/PID pair.  All ports are kept track of in a
python dict named "ports".
"""

import logging

try:
    import makerbot_pyserial.tools.list_ports as lp
    list_ports_generator = lp.list_ports_by_vid_pid
except ImportError:
    import warnings
    warnings.warn("No VID/PID detection in this version of PySerial; Automatic machine detection disabled.")
    # We're using legacy pyserial. list_port_generator is an empty iterator.

    def list_ports_generator():
        return
        yield

## Tools for using the global singleton MachineDetector
gMachineDetector = None


def get_gMachineDetector():
    """ use a global singleton MachineDetector """
    global gMachineDetector
    if(gMachineDetector is None):
        gMachineDetector = MachineDetector()
    return gMachineDetector


# machine USB classes IE what VID/PID can map to what machine profiles
gMachineClasses = {
    #Replicator 2(legacy) is for the Rep2 and 2X bots that share a PID
    'The Replicator 2(legacy)':
    {'vid': 0x23C1, 'pid': [0xB015], 'machineProfiles': '.*Replicator2'},
    'The Replicator 2':
    {'vid': 0x23C1, 'pid': [0xB016], 'machineProfiles': '.*Replicator2'},
    'The Replicator 2X':
    {'vid': 0x23C1, 'pid': [0xB017], 'machineProfiles': '.*Replicator2X'},
    'The Replicator':
    {'vid': 0x23C1, 'pid': [0xD314], 'machineProfiles': '.*Replicator'},
    'MightyBoard':
    {'vid': 0x23C1, 'pid': [0xB404], 'machineProfiles': '.*Replicator'},
    'TOM FTDI':
    {'vid': 0x0403, 'pid': [0x6001], 'machineProfiles': '.*TOMStepstruder'},
    'TOM 8U2':
    {'vid': 0x2341, 'pid': [0x0010], 'machineProfiles': '.*TOMStepstruder'},
}


def get_vid_pid_by_name(name):
    """
    @name name of a 'class' of machines 'TOM', 'The Replicator 2'
    @return a tuple of vid/pid, or a tuple of (None,None) if there
    is an error.
    NOTE: at this low level, 'MightyBoard's are treated separate from
    final 'The Replicator's
    """
    if name in gMachineClasses.keys():
        return (gMachineClasses[name]['vid'],
                gMachineClasses[name]['pid'][0])
    return (None, None)


class MachineDetector(object):
    """ Class used to detect machines, and query basic information from
    them. This is used to use MakerBot's pyserial to detect machines. """

    def __init__(self):
        self._log = logging.getLogger(self.__class__.__name__)
        self.machines_recently_seen = {}
        # ^ Bots seen since the inception of this object
        self.machines_just_seen = {}
        # ^ Bots seen in the last scan,
        self.list_ports_by_vid_pid = list_ports_generator
        # ^ Save func as a variable for testing purposes. hacky

    def get_machine_name_from_vid_pid(self, vid, pid):
        machine_name = None
        for key in gMachineClasses:
            if gMachineClasses[key]['vid'] == vid and (pid in gMachineClasses[key]['pid']):
                machine_name = key
                break
        return machine_name

    def scan(self, machineTypes=None):
        """ scans for connected machines, updates internal list of machines
        based on scan results
        @param machineTypes. An individual MachineClass name, or a list
        of machine class names
        """
        # scan for all machine types
        scanNameList = []
        if machineTypes is None:
            scanNameList.extend(gMachineClasses.keys())
        elif isinstance(machineTypes, str) or isinstance(machineTypes, unicode):
            scanNameList.append(machineTypes)
        else:
            scanNameList.extend(machineTypes)
        # Empty the machines just seen list. We are rescanning
        # all machines connected to the system.
        self.machines_just_seen = {}
        for machineClass in scanNameList:
            self._log.debug("scanning for MachineClass %s", str(machineClass))
            #Not all machine classes have a defined VID/PID
            try:
                vid = gMachineClasses[machineClass]['vid']
                pid_list = gMachineClasses[machineClass]['pid']
               
                new_machines = []
                for pid in pid_list:
                  new_machines.extend(self.list_ports_by_vid_pid(vid, pid))

                for machine in list(new_machines):
                    self.machines_just_seen[machine['port']] = machine
                self.machines_recently_seen.update(self.machines_just_seen)
            except KeyError:
                continue  # The machine doesnt have a VID/PID, so we cant scan for it

    def vid_pid_from_portname(self, portname):
        """ return pid/vid based on a passed portname."""
        vid = None
        pid = None
        ports_to_check = self.get_tty_and_cu(portname)
        available_machines = self.get_available_machines()
        set_available = set(available_machines)
        intersection = ports_to_check.intersection(set_available)
        if len(intersection) > 0:
            usable_port = list(intersection)[0]
            vid = available_machines[usable_port]['VID']
            pid = available_machines[usable_port]['PID']
        return vid, pid

    def get_tty_and_cu(self, portname):
        ports_to_check = set([portname])
        if '/dev/tty.' in portname:
            ports_to_check.update([portname.replace('/dev/tty.', '/dev/cu.')])
        elif '/dev/cu.' in portname:
            ports_to_check.update([portname.replace('/dev/cu.', '/dev/tty.')])
        return ports_to_check

    def get_first_machine(self, machineType=None):
        """ returns a list of machines sorted by currently connected ports
        @return a port data dict of {'vid':vid, 'pid':pid 'port':port [...]}
        """
        for b in self.machines_just_seen.keys():
            return b
        return None

    def get_available_machines(self, machineTypes=None):
        """ returns a list of machines sorted by currently connected ports
        port_data_dict includes {'vid':vid, 'pid':pid 'port':port [...]}
        @return dict of {'portname',port_data_dict"""

        self.scan(machineTypes)
        return self.machines_just_seen
