import re
from makerbot_pyserial.tools.list_ports import comports

""" 
Contains tools for taking a serial object from the standard serial module,
and intellegently parse out and use PID/VID and iSerial values from it
"""   

def portdict_from_port(port):
    """
    Given a port object from serial.comport() create a vid/pid/iSerial/port dict if possible

    @param str identifier_string: String retrieved from a serial port
    @return dict: A dictionary VID/PID/iSerial/Port.  On parse error dict contails only 'Port':port'
    """
    identifier_string = port[-1]
    data = {'blob':port}
    data['port'] = port[0]
    try:
        if 'SNR=None' in identifier_string or 'SNR' not in identifier_string:
            vid, pid = re.search('VID:PID=([0-9A-Fa-f]{1,4}):([0-9A-Fa-f]{1,4})', identifier_string).groups()
            data['VID'] = int(vid,16)
            data['PID'] = int(pid,16)
            data['iSerial'] = '00000000000000000000'
        else:
            vid, pid, serial_number = re.search('VID:PID=([0-9A-Fa-f]{1,4}):([0-9A-Fa-f]{1,4}) SNR=(\w*)', identifier_string).groups()
            data['VID'] = int(vid,16)
            data['PID'] = int(pid,16)
            data['iSerial'] = serial_number
    except AttributeError:
        pass
    return data   



def list_ports_by_vid_pid(vid=None, pid=None):
    """ Given a VID and PID value, scans for available port, and
	if matches are found, returns a dict of 'VID/PID/iSerial/Port'
	that have those values.

    @param int vid: The VID value for a port
    @param int pid: The PID value for a port
    @return iterator: Ports that are currently active with these VID/PID values
    """
    #Get a list of all ports
    ports = comports()
    return filter_ports_by_vid_pid(ports, vid, pid)

def filter_ports_by_vid_pid(ports,vid=None,pid=None):
    """ Given a VID and PID value, scans for available port, and
	f matches are found, returns a dict of 'VID/PID/iSerial/Port'
	that have those values.

    @param list ports: Ports object of valid ports
    @param int vid: The VID value for a port
    @param int pid: The PID value for a port
    @return iterator: Ports that are currently active with these VID/PID values
    """
    for port in ports:
        #Parse some info out of the identifier string
        try: 
            data = portdict_from_port(port)
            if vid == None or data['VID'] == vid:
                if  pid == None or  data['PID'] == pid:
            	    yield data
        except:
            pass
