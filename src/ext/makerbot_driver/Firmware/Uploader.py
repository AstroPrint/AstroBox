from __future__ import absolute_import

import json
import os
import subprocess
import platform
import urllib2
import logging
import urlparse
import tempfile
import serial

import makerbot_driver


def _check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        e = subprocess.CalledProcessError(retcode, cmd)
        setattr(e, 'output', output)
        raise e
    return output


class Uploader(object):
    """ Firmware Uploader is used to send firmware to a 3D printer."""

    def __init__(self, source_url=None, dest_path=None, autoUpdate=True, path_to_eeprom=None, avrdude_exe=None, avrdude_conf_file=None):
        """Build an uploader.
        @param source_url: specify a url to fetch firmware metadata from. Can be a directory
        @param dest_path: path to use as the local file store location
        @param autoUpdate: automatically and immedately fetch machine data
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.product_filename = 'products.json'
        self.source_url = source_url if source_url else 'http://firmware.makerbot.com'
        self.dest_path = dest_path if dest_path else tempfile.mkdtemp()

        self.run_subprocess = _check_output
        self.urlopen = urllib2.urlopen
        self.path_to_eeprom = path_to_eeprom if path_to_eeprom else os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            '..',
            'EEPROM',
        )
        self._avrdude_exe = avrdude_exe
        self._avrdude_conf_file = avrdude_conf_file
        if autoUpdate:
            self.update()

    def compatible_firmware(self, firmware_version, software_variant):
        """
        Determines if a firmware version is compatible with the current driver

        @param str firmware_version: Firmware version to check
        @return bool: True if firmware is compatible, false otherwise
        """
        map_name = makerbot_driver.EEPROM.eeprom_map_name % (firmware_version, software_variant)
        return map_name in os.listdir(self.path_to_eeprom)

    def pathjoin(self, base, resource):
        """ joins URL or filename paths to find a resource relative to base"""
        if(base.startswith('http://')):
            return urlparse.urljoin(base, resource)
        return os.path.normpath(os.path.join(base, resource))

    def update(self):
        """
        Update should be called before any firmware loading is done, to ensure the
        most up-to-date information is being used.
        """
        self._logger.info('{"event":"updating_updater"}')
        self._pull_products()

    def _pull_products(self):
        """
        Pulls the most recent products.json file and, using that
        to update internal manchine lists and metadata
        """
        product_filename = self.pathjoin(
            self.source_url, self.product_filename)
        filename = self.wget(product_filename)
        #Assuming wget works, this shouldnt be a problem
        self.products = self.load_json_values(filename)
        self.get_machine_json_files()

    def get_machine_json_files(self):
        """
        Assuming a product.json file has been pulled and loaded,
        explores that products.json file and wgets all machine json files.
        """
        machines = self.products['ExtrusionPrintersV2']
        for machine in machines:
            f = self.products['ExtrusionPrintersV2'][machine]
            url = self.pathjoin(
                self.source_url, self.products['ExtrusionPrintersV2'][machine])
            self.wget(url)

    def wget(self, url):
        """
        Gets a certain file from a url and copies it into
        the current working directory.  If the url is stored
        locally, we copy that file.  Otherwise we pull it from
        the internets.

        @param str url: The url we want to wget
        @return file: local filename of the resource
        """
        local_path = os.path.basename(url)
        local_path = os.path.join(self.dest_path, local_path)
        if os.path.isfile(url):
            if not url == local_path:
                self._logger.info(
                    '{"event":"copying_local_file", "file":%s}' % url)
                import shutil
                shutil.copy(url, local_path)
        else:
            self._logger.info('{"event":"downloading_url", "url":%s}' % url)
            try:
                #Download the file
                dl_file = self.urlopen(url)
            except urllib2.URLError as e:
                # Means we have no internet connection
                raise e
            #Write out the file
            with open(local_path, 'w') as f:
                f.write(dl_file.read())
        return local_path

    def load_json_values(self, path):
        with open(path) as f:
            return json.load(f)

    def get_firmware_values(self, machine):
        """
        Given a machine name, retrieves the associated .json file and parses
        out its values.

        @param str machine: The machine we want information about
        @return dict values: The values parsed out of the machine board profile
        """
        path = os.path.join(
            self.dest_path,
            self.products['ExtrusionPrintersV2'][machine],
        )
        path = os.path.normpath(path)
        return self.load_json_values(path)

    def list_firmware_versions(self, machine, pid):
        """
        Given a machine name, returns all possible versions we can upload to

        @param str machine: The machine we want information about
        @return list versions: The versions we can upload
        """
        values = self.get_firmware_values(machine)
        versions = []
        for version in values['PID'][pid]['versions']:
            descriptor = values['PID'][pid]['versions'][version][1]
            versions.append([version, descriptor])
        return versions

    def list_machines(self):
        """
        Lists all the machines we can upload firmware to

        @return iterator machines: The machines we can upload firmware to
        """
        return self.products['ExtrusionPrintersV2'].keys()

        self.assertEqual(expected_profile, getattr(return_obj, 'profile'))
        self.assertEqual(expected_parser, getattr(return_obj, 'gcodeparser'))

    def download_firmware(self, machine, pid, version):
        values = self.get_firmware_values(machine)
        values = values['PID'][pid]
        try:
            hex_file = str(values['versions'][version][0])
        except KeyError:
            raise makerbot_driver.Firmware.UnknownVersionError
        hex_file_url = self.pathjoin(self.source_url, hex_file)
        hex_file_path = self.wget(hex_file_url)
        return hex_file_path

    def parse_avrdude_command(self, port, machine, pid, filename, local_avr=True):
        """
        Given a port, machine name, and firmware filename, parses out a command
        that invokes avrdude

        @param str port: The port the machine is connected to
        @param str machine: The machine we are uploading to
        @param str filename: The firmware we want to upload
        @return str command: The command that invokes avrdude
        """
        values = self.get_firmware_values(machine)
        values = values['PID'][pid]
        if None is not self._avrdude_exe:
            process = self._avrdude_exe
        else:
            process = 'avrdude'
            if platform.system() == "Windows":
                process += ".exe"
            if local_avr:
                path = os.path.join(
                    os.path.abspath(os.path.dirname(__file__)),
                    process,
                )
                process = path
        if None is not self._avrdude_conf_file:
            config_file = self._avrdude_conf_file
        else:
            config_file = os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                'avrdude.conf'
            )
        flags = []
        #get the part
        flags.append('-C' + config_file)
        flags.append('-p' + str(values['part']))
        #get the baudrate
        flags.append('-b' + str(values['baudrate']))
        #get the programmer
        flags.append('-c' + str(values['programmer']))
        #get the port
        if platform.system() == "Windows":
            # NOTE: Windows needs the port name in this ridiculous format or ports
            # above COM4 will not work.
            flags.append('-P\\\\.\\' + port)
        else:
            flags.append('-P' + port)
        #get the operation
        flags.append('-U' + 'flash:w:' + filename + ':i')
        return [process] + flags

    def toggle_machine(self, port):
        s = serial.Serial(port)
        s.baudrate = 9600
        s.baudrate = 115200
        s.close()

    def upload_firmware(self, port, machine, pid, filename):
        """
        Given a port, machine name, and firmware filename, invokes avrdude to
        upload that firmware to a specific type of machine.

        @param str port: The port the machine is connected to
        @param str machine: The machine we are uploading to
        @param str filename: The firmware we want to upload
        """
        self._logger.info('{"event":"uploading_firmware", "port":%s, "machine":%s, "pid":%s, "filename":%s}', port, machine, pid, filename)
        call = self.parse_avrdude_command(port, machine, pid, filename)
        self.toggle_machine(port)
        try:
            try:
                self._logger.info('{"event":"trying local avrdude"}')
                output = self.run_subprocess(call, stderr=subprocess.STDOUT)
                self._logger.debug('output=%r', output)
            except OSError:
                self._logger.info('{"event":"trying external avrdude"}')
                call = self.parse_avrdude_command(
                    port, machine, pid, filename, local_avr=False)
                output = self.run_subprocess(call, stderr=subprocess.STDOUT)
                self._logger.debug('output=%r', output)
        except subprocess.CalledProcessError as e:
            self._logger.error('avrdude failed: %s', e.output)
            raise
