from __future__ import absolute_import, print_function

import os
import threading

import makerbot_driver

class ReturnObject(object):

    def __init__(self):
        pass


class MachineFactory(object):
    """This class is a factory for building machine drivers from
    a port connection. This class will take a connection, query it
    to verify it is a geunine 3d printer (or other device we can control)
    and build the appropritae machine type/version/etc from that.
    """
    def __init__(self, profile_dir=None):
        if profile_dir:
            self.profile_dir = profile_dir
        else:
            self.profile_dir = os.path.join(
                os.path.abspath(os.path.dirname(__file__)), 'profiles',)

    def create_inquisitor(self, portname):
        """
        This is made to ameliorate testing, this having to
        assign internal objects with <obj>.<internal_obj> = <obj> is a
        pain.
        """
        return MachineInquisitor(portname)

    def build_from_port(self, portname, leaveOpen=True, condition=None):
        """
        Returns a tuple of an (s3gObj, ProfileObj)
        for a machine at port portname
        """
        machineInquisitor = self.create_inquisitor(portname)
        if None is condition:
            condition = threading.Condition()
        s3gBot, machine_setup_dict = machineInquisitor.query(condition, leaveOpen)

        profile_regex = self.get_profile_regex(machine_setup_dict)
        matches = makerbot_driver.search_profiles_with_regex(
            profile_regex, self.profile_dir)
        matches = list(matches)
        return_object = ReturnObject()
        attrs = ['s3g', 'profile', 'gcodeparser']
        for a in attrs:
            setattr(return_object, a, None)
        if len(matches) > 0:
            bestProfile = matches[0]
            setattr(return_object, 's3g', s3gBot)
            profile = makerbot_driver.Profile(bestProfile, self.profile_dir)
            profile.values['print_to_file_type']=[machine_setup_dict['print_to_file_type']]
            profile.values['software_variant'] = machine_setup_dict['software_variant']
            profile.values['tool_count_error'] = machine_setup_dict['tool_count_error']
            setattr(return_object, 'profile', profile)
            parser = makerbot_driver.Gcode.GcodeParser()
            parser.s3g = s3gBot
            parser.state.profile = getattr(return_object, 'profile')
            setattr(return_object, 'gcodeparser', parser)
        return return_object

    def create_s3g(self, portname):
        """
        This is made to ameliorate testing.  Otherwise we would
        not be able to reliably test the build_from_port function
        w/o being permanently attached to a specific port.
        """
        return makerbot_driver.s3g.from_filename(portname)

    def get_profile_regex(self, machine_setup_dict):
        """
        Decision tree for machine decisions.

        @param dict machine_setup_dict: A dictionary containing
          information about the connected machine
        @return str
        """
        regex = None
        #First check for VID/PID matches
        if 'vid' in machine_setup_dict and 'pid' in machine_setup_dict:
            regex = self.get_profile_regex_has_vid_pid(machine_setup_dict)
        if '.*Replicator2' == regex:
            #if the pid does not belong to the legacy Rep2's then no toolcount
            #inquiry is necessary, return the Rep2 regex
            if(makerbot_driver.get_vid_pid_by_name('The Replicator 2')[1] ==
              machine_setup_dict['pid']):
                pass
            elif regex and machine_setup_dict.get('tool_count', 0) == 2:
                regex = regex + 'X'
            elif machine_setup_dict.get('tool_count', 0) != 1:
                regex = None
        elif '.*Replicator2X' == regex:
            pass
        else:
            if regex and machine_setup_dict.get('tool_count', 0) == 1:
                regex = regex + 'Single'
            elif regex and machine_setup_dict.get('tool_count', 0) == 2:
                regex = regex + 'Dual'
            else:
              regex = None
        return regex

    def get_profile_regex_has_vid_pid(self, machine_setup_dict):
        """If the machine has a VID and PID, we can assume it is part of
        the generation of machines that also have a tool_count.  We use the
        tool_count at the final criterion to narrow our search.
        """
        vid_pid_matches = []
        for machine in makerbot_driver.gMachineClasses.values():
            if machine['vid'] == machine_setup_dict['vid'] and machine_setup_dict['pid'] in machine['pid']:
                return machine['machineProfiles']
        return None


class MachineInquisitor(object):
    def __init__(self, portname):
        """ build a machine Inqusitor for an exact port"""
        self._portname = portname

    def create_s3g(self, condition):
        """
        This is made to ameliorate testing, this having to
        assign internal objects with <obj>.<internal_obj> = <obj> is a
        pain.
        """
        return makerbot_driver.s3g.from_filename(self._portname, condition)

    def query(self, condition, leaveOpen=True):
        """
        open a connection to a machine and  query a machine for
        key settings needed to construct a machine from a profile

        @param leaveOpen IF true, serial connection to the machine is left open.
        @return a tuple of an (s3gObj, dictOfSettings
        """
        import makerbot_driver.s3g as s3g
        settings = {}
        s3gDriver = self.create_s3g(condition)
        s3gDriver.clear_buffer()
        settings['vid'], settings['pid'] = s3gDriver.get_vid_pid()
        firmware_version = s3gDriver.get_version()
        
        try:   
            s3gDriver.init_eeprom_reader(firmware_version) 
        except  makerbot_driver.EEPROM.MissingEepromMapError:
            pass
  
        settings['tool_count'] = s3gDriver.get_toolhead_count()
        if settings['tool_count'] not in makerbot_driver.constants.valid_toolhead_counts : 
            settings['tool_count'] = 1
            settings['tool_count_error'] = True
        else:
            settings['tool_count_error'] = False

        try:
            version_settings = s3gDriver.get_advanced_version();
            settings['software_variant'] = hex(version_settings['SoftwareVariant'])
            if version_settings['SoftwareVariant'] != 0:
                s3gDriver.set_print_to_file_type('x3g')
                settings['print_to_file_type'] = 'x3g'
            else: 
                s3gDriver.set_print_to_file_type('s3g')
                settings['print_to_file_type'] = 's3g'

        except makerbot_driver.CommandNotSupportedError:
            s3gDriver.set_print_to_file_type('s3g')
            settings['software_variant'] = hex(0)
            settings['print_to_file_type'] = 's3g'

        if len(settings['software_variant'].split('x')[1]) == 1:
            settings['software_variant'] = settings['software_variant'].replace('x', 'x0')
            
        if not leaveOpen:
            s3gDriver.close()
        return s3gDriver, settings
