import ctypes
import _winreg as winreg
import itertools
import sets
import re
import logging

def ValidHandle(value, func, arguments):
    if value == 0:
        raise ctypes.WinError()
    return value

import makerbot_pyserial
from serial.win32 import ULONG_PTR, is_64bit
from ctypes.wintypes import HANDLE
from ctypes.wintypes import BOOL
from ctypes.wintypes import HWND
from ctypes.wintypes import DWORD
from ctypes.wintypes import WORD
from ctypes.wintypes import LONG
from ctypes.wintypes import ULONG
from ctypes.wintypes import LPCSTR
from ctypes.wintypes import HKEY
from ctypes.wintypes import BYTE

NULL = 0
HDEVINFO = ctypes.c_void_p
PCTSTR = ctypes.c_char_p
CHAR = ctypes.c_char
LPDWORD = PDWORD = ctypes.POINTER(DWORD)
#~ LPBYTE = PBYTE = ctypes.POINTER(BYTE)
LPBYTE = PBYTE = ctypes.c_void_p        # XXX avoids error about types
PHKEY = ctypes.POINTER(HKEY)

ACCESS_MASK = DWORD
REGSAM = ACCESS_MASK

def byte_buffer(length):
    """Get a buffer for a string"""
    return (BYTE*length)()

def string(buffer):
    s = []
    for c in buffer:
        if c == 0: break
        s.append(chr(c & 0xff)) # "& 0xff": hack to convert signed to unsigned
    return ''.join(s)


class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', DWORD),
        ('Data2', WORD),
        ('Data3', WORD),
        ('Data4', BYTE*8),
    ]
    def __str__(self):
        return "{%08x-%04x-%04x-%s-%s}" % (
            self.Data1,
            self.Data2,
            self.Data3,
            ''.join(["%02x" % d for d in self.Data4[:2]]),
            ''.join(["%02x" % d for d in self.Data4[2:]]),
        )

class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('ClassGuid', GUID),
        ('DevInst', DWORD),
        ('Reserved', ULONG_PTR),
    ]
    def __str__(self):
        return "ClassGuid:%s DevInst:%s" % (self.ClassGuid, self.DevInst)
PSP_DEVINFO_DATA = ctypes.POINTER(SP_DEVINFO_DATA)

class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('InterfaceClassGuid', GUID),
        ('Flags', DWORD),
        ('Reserved', ULONG_PTR),
    ]
    def __str__(self):
        return "InterfaceClassGuid:%s Flags:%s" % (self.InterfaceClassGuid, self.Flags)
PSP_DEVICE_INTERFACE_DATA = ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)

PSP_DEVICE_INTERFACE_DETAIL_DATA = ctypes.c_void_p

setupapi = ctypes.windll.LoadLibrary("setupapi")
SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList
SetupDiDestroyDeviceInfoList.argtypes = [HDEVINFO]
SetupDiDestroyDeviceInfoList.restype = BOOL

SetupDiGetClassDevs = setupapi.SetupDiGetClassDevsA
SetupDiGetClassDevs.argtypes = [ctypes.POINTER(GUID), PCTSTR, HWND, DWORD]
SetupDiGetClassDevs.restype = HDEVINFO
SetupDiGetClassDevs.errcheck = ValidHandle

SetupDiEnumDeviceInterfaces = setupapi.SetupDiEnumDeviceInterfaces
SetupDiEnumDeviceInterfaces.argtypes = [HDEVINFO, PSP_DEVINFO_DATA, ctypes.POINTER(GUID), DWORD, PSP_DEVICE_INTERFACE_DATA]
SetupDiEnumDeviceInterfaces.restype = BOOL

SetupDiGetDeviceInterfaceDetail = setupapi.SetupDiGetDeviceInterfaceDetailA
SetupDiGetDeviceInterfaceDetail.argtypes = [HDEVINFO, PSP_DEVICE_INTERFACE_DATA, PSP_DEVICE_INTERFACE_DETAIL_DATA, DWORD, PDWORD, PSP_DEVINFO_DATA]
SetupDiGetDeviceInterfaceDetail.restype = BOOL

SetupDiGetDeviceRegistryProperty = setupapi.SetupDiGetDeviceRegistryPropertyA
SetupDiGetDeviceRegistryProperty.argtypes = [HDEVINFO, PSP_DEVINFO_DATA, DWORD, PDWORD, PBYTE, DWORD, PDWORD]
SetupDiGetDeviceRegistryProperty.restype = BOOL

SetupDiOpenDevRegKey = setupapi.SetupDiOpenDevRegKey
SetupDiOpenDevRegKey.argtypes = [HDEVINFO, PSP_DEVINFO_DATA, DWORD, DWORD, DWORD, REGSAM]
SetupDiOpenDevRegKey.restype = HKEY

advapi32 = ctypes.windll.LoadLibrary("Advapi32")
RegCloseKey = advapi32.RegCloseKey
RegCloseKey.argtypes = [HKEY]
RegCloseKey.restype = LONG

RegQueryValueEx = advapi32.RegQueryValueExA
RegQueryValueEx.argtypes = [HKEY, LPCSTR, LPDWORD, LPDWORD, LPBYTE, LPDWORD]
RegQueryValueEx.restype = LONG


GUID_CLASS_COMPORT = GUID(0x86e0d1e0L, 0x8089, 0x11d0,
    (BYTE*8)(0x9c, 0xe4, 0x08, 0x00, 0x3e, 0x30, 0x1f, 0x73))

DIGCF_PRESENT = 2
DIGCF_DEVICEINTERFACE = 16
INVALID_HANDLE_VALUE = 0
ERROR_INSUFFICIENT_BUFFER = 122
SPDRP_HARDWAREID = 1
SPDRP_FRIENDLYNAME = 12
ERROR_NO_MORE_ITEMS = 259
DICS_FLAG_GLOBAL = 1
DIREG_DEV = 0x00000001
KEY_READ = 0x20019
REG_SZ = 1

# workaround for compatibility between Python 2.x and 3.x
PortName = makerbot_pyserial.to_bytes([80, 111, 114, 116, 78, 97, 109, 101]) # "PortName"

def comports():
    """This generator scans the device registry for com ports and yields port, desc, hwid"""
    g_hdi = SetupDiGetClassDevs(ctypes.byref(GUID_CLASS_COMPORT), None, NULL, DIGCF_PRESENT|DIGCF_DEVICEINTERFACE);
    #~ for i in range(256):
    for dwIndex in range(256):
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(did)

        if not SetupDiEnumDeviceInterfaces(g_hdi, None, ctypes.byref(GUID_CLASS_COMPORT), dwIndex, ctypes.byref(did)):
            if ctypes.GetLastError() != ERROR_NO_MORE_ITEMS:
                raise ctypes.WinError()
            break

        dwNeeded = DWORD()
        # get the size
        if not SetupDiGetDeviceInterfaceDetail(g_hdi, ctypes.byref(did), None, 0, ctypes.byref(dwNeeded), None):
            # Ignore ERROR_INSUFFICIENT_BUFFER
            if ctypes.GetLastError() != ERROR_INSUFFICIENT_BUFFER:
                raise ctypes.WinError()
        # allocate buffer
        class SP_DEVICE_INTERFACE_DETAIL_DATA_A(ctypes.Structure):
            _fields_ = [
                ('cbSize', DWORD),
                ('DevicePath', CHAR*(dwNeeded.value - ctypes.sizeof(DWORD))),
            ]
            def __str__(self):
                return "DevicePath:%s" % (self.DevicePath,)
        idd = SP_DEVICE_INTERFACE_DETAIL_DATA_A()
        if is_64bit():
            idd.cbSize = 8
        else:
            idd.cbSize = 5
        devinfo = SP_DEVINFO_DATA()
        devinfo.cbSize = ctypes.sizeof(devinfo)
        if not SetupDiGetDeviceInterfaceDetail(g_hdi, ctypes.byref(did), ctypes.byref(idd), dwNeeded, None, ctypes.byref(devinfo)):
            raise ctypes.WinError()

        # hardware ID
        szHardwareID = byte_buffer(250)
        if not SetupDiGetDeviceRegistryProperty(g_hdi, ctypes.byref(devinfo), SPDRP_HARDWAREID, None, ctypes.byref(szHardwareID), ctypes.sizeof(szHardwareID) - 1, None):
            # Ignore ERROR_INSUFFICIENT_BUFFER
            if GetLastError() != ERROR_INSUFFICIENT_BUFFER:
                raise ctypes.WinError()

        # friendly name
        szFriendlyName = byte_buffer(250)
        if not SetupDiGetDeviceRegistryProperty(g_hdi, ctypes.byref(devinfo), SPDRP_FRIENDLYNAME, None, ctypes.byref(szFriendlyName), ctypes.sizeof(szFriendlyName) - 1, None):
            # Ignore ERROR_INSUFFICIENT_BUFFER
            if ctypes.GetLastError() != ERROR_INSUFFICIENT_BUFFER:
                #~ raise IOError("failed to get details for %s (%s)" % (devinfo, szHardwareID.value))
                port_name = None
        else:
            # the real com port name has to read differently...
            hkey = SetupDiOpenDevRegKey(g_hdi, ctypes.byref(devinfo), DICS_FLAG_GLOBAL, 0, DIREG_DEV, KEY_READ)
            port_name_buffer = byte_buffer(250)
            port_name_length = ULONG(ctypes.sizeof(port_name_buffer))
            RegQueryValueEx(hkey, PortName, None, None, ctypes.byref(port_name_buffer), ctypes.byref(port_name_length))
            RegCloseKey(hkey)
            yield string(port_name_buffer), string(szFriendlyName), string(szHardwareID)

    SetupDiDestroyDeviceInfoList(g_hdi)


class VIDPIDAccessError(Exception):
    """a VIDPIDAccessError is indicative of the specific VID/PID
    registry key missing.  This happens if a windows machine has never
    seen a Replicator before.
    """
    def __init__(self):
        pass

class COMPORTAccessError(Exception):
    """A COMPORTAccessError is indicative of the SERIALCOMM key
    missing.  This actually happens every time (I think) windows
    resets.  Its expected the layer on top of this one
    will catch this error and report accordingly.
    """
    def __init__(self):
        pass

def convert_to_16_bit_hex(i):
    """Given an int value >= 0 and <= 65535,
    converts it to a 16 bit hex number (i.e.
    0xffff, 0x0001)

    @param int i: The number to convert
    @return str h: The hex number to return
    """
    the_min = 0
    the_max = 65535
    if i < the_min or i > the_max:
        raise ValueError
    h = hex(i).replace('0x', '')
    h = h.upper()
    while len(h) < 4:
        h = '0' + h
    return h

def filter_usb_dev_keys(base, vid, pid):
    vidpattern = "[0-9A-Fa-f]{4}"
    pidpattern = "[0-9A-Fa-f]{4}"

    if vid is not None:
        vidpattern = convert_to_16_bit_hex(vid)
    if pid is not None:
        pidpattern = convert_to_16_bit_hex(pid)

    pattern = re.compile("VID_(%s)&PID_(%s)" %(vidpattern, pidpattern), re.IGNORECASE)

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
    except WindowsError as e:
        logging.getLogger('list_ports_windows').error('WindowsError: ' + e.strerror)
        raise VIDPIDAccessError

    for devnum in itertools.count():
        try:
            devname = winreg.EnumKey(key, devnum)
        except EnvironmentError as e:
            break

        m = pattern.match(devname)
        if m is not None:
            yield {'key': base + devname,
                   'VID': m.group(1),
                   'PID': m.group(2)}

ftdi_vid_pid_regex = re.compile('VID_(\d+)[^+]*\+PID_(\d+)[^+]*\+(.*)')
def enumerate_ftdi_ports_by_vid_pid(vid, pid):
    """Lists all the FTDI ports in the FTDIBUS
    registry entry with a given VID/PID pair.

    @param int vid: The Vendor ID
    @param int pid: The Product ID
    @return iterator: An iterator of information for each port with these VID/PID values
    """
    base = "SYSTEM\\CurrentControlSet\\Enum\\FTDIBUS\\"

    try:
        ftdibus = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
    except WindowsError as e:
        logging.getLogger('list_ports_windows').debug('WindowsError: ' + e.strerror)
        # If a WindowsError occurs there has never been an FTDI plugged in.
        # There's nothing to iterate, so we raise a StopIteration exception.
        raise StopIteration

    try:
        for index in itertools.count():
            ftdi_port = winreg.EnumKey(ftdibus, index)

            ftdi_data = ftdi_vid_pid_regex.match(ftdi_port)
            if None != ftdi_data:

                current_vid = ftdi_data.group(1)
                current_pid = ftdi_data.group(2)
                not_iSerial = ftdi_data.group(3)

                if (vid == None or vid == current_vid) and (pid == None or pid == current_pid):
                    try:
                        device_params = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                                       base + ftdi_port + '\\0000\\Device Parameters')
                        for param in itertools.count():
                            name, value, type = winreg.EnumValue(device_params, param)
                            if 'PortName' == name:
                                port_name = value
                                break
                    except WindowsError as e:
                        logging.getLogger('list_ports_windows').error('WindowsError: ' + e.strerror)
                        # didn't find a portname? not sure if this is a
                        # problem, or if this will even ever happen.
                        continue

                    yield {'VID': current_vid,
                           'PID': current_pid,
                           'iSerial': not_iSerial,
                           'PortName': port_name}
            else:
                logging.getLogger('list_ports_windows').debug('FTDI does not match pattern.')

            index += 1
    except WindowsError as e:
        # the end of the FTDI list
        raise StopIteration


def enumerate_recorded_ports_by_vid_pid(vid, pid):
    """Given a port name, checks the dynamically
    linked registries to find the VID/PID values
    associated with this port.

    @param int vid: The Vendor ID
    @param int pid: The Product ID
    @return iterator: An iterator of information for each port with these VID/PID values
    """
    base = "SYSTEM\\CurrentControlSet\\Enum\\USB\\"
    #Convert pid/hex to upper case hex numbers
    #path = get_path(convert_to_16_bit_hex(vid), convert_to_16_bit_hex(pid))

    if vid is not None and pid is not None:
        vidpidkeys = [{'key' : get_path(convert_to_16_bit_hex(vid), convert_to_16_bit_hex(pid)),
                       'VID' : convert_to_16_bit_hex(vid),
                       'PID' : convert_to_16_bit_hex(pid)}]
    else:
        vidpidkeys = filter_usb_dev_keys(base, vid, pid)

    for vidpidkey_details in vidpidkeys:
        vidpidkey = vidpidkey_details['key']

        try:
            #The key is the VID PID address for all possible Rep connections
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, vidpidkey)
        except WindowsError as e:
            #Windows registry seems to sometimes enumerates keys that don't exist
            continue
        #For each subkey of key
        for i in itertools.count():
           try:
               #we grab the keys name
               child_name = winreg.EnumKey(key, i) #EnumKey gets the NAME of a subkey
               #Open a new key which is pointing at the node with the info we need
               new_path = "%s\\%s\\Device Parameters" %(vidpidkey, child_name)
               try:
                   child_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, new_path)
               except WindowsError as e:
                   continue #not all com ports are fully filled out

               #child_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path+'\\'+child_name+'\\Device Parameters')
               comport_info = {'iSerial' : child_name,
                               'VID' : vidpidkey_details['VID'],
                               'PID' : vidpidkey_details['PID']}

               #For each bit of information in this new key
               for j in itertools.count():
                   try:
                       #Grab the values for a certain index
                       child_values = winreg.EnumValue(child_key, j)
                       comport_info[child_values[0]] = child_values[1]
                   #We've reached the end of the tree
                   except EnvironmentError:
                      yield comport_info
                      break
           #We've reached the end of the tree
           except EnvironmentError:
               break

def get_path(vid, pid):
    """
    The registry path is dependent on the PID values
    we are looking for.

    @param str pid: The PID value in base 16
    @param str vid: The VID value in base 16
    @return str The path we are looking for
    """
    path = "SYSTEM\\CurrentControlSet\\Enum\\USB\\"
    target = "VID_%s&PID_%s" %(vid, pid)
    return path+target

def enumerate_active_serial_ports():
    """ Uses the Win32 registry to return an
    iterator of serial (COM) ports
    existing on this computer.

    NB: When windows resets, it removes the SERIALCOMM key.
    This means that if we try to scan before anything has been
    plugged in, we will raise COMPORTAccessErrors.  Its expected
    that the layer on top of this one will catch those errors
    and report back accordingly.
    """
    path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
    try:
        #Opening the KEY to a certain path
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except WindowsError:
        raise COMPORTAccessError

    #For each value attached to the above key
    for i in itertools.count():
        try:
            #Get the next value and yield it
            val = winreg.EnumValue(key, i)
            yield val
        #We are done traversing this tree
        except EnvironmentError:
            break

def portdict_from_sym_name(sym_name,port):
    """
    Windows stores the VID, PID, iSerial (along with other bits of info)
    in a single string separated by a # sign.  We parse that information out
    and export it.

    @param str sym_name: windows usb id string. Z.b. "horrible_stuff#VID_0000&PID_1111#12345678901234567890"
    @param str port: The port we are considering
    @return dict: A dictionary VID/PID/iSerial/Port.  On parse error dict contails only 'Port':port'
    """
    dict = {'port':port}
    try:
        sym_name = sym_name.upper()
        sym_list = sym_name.split('#')
        v_p = sym_list[1]
        v_p = v_p.split('&')
        v_p.sort() #Windows labels their VID/PIDs, so we sort so we know which is which

        #Convert PID into an int
        PID = v_p[0].replace('PID_', '')
        PID = int(PID, 16)
        dict['PID'] = PID

        #Convert VID into an int
        VID = v_p[1].replace('VID_', '')
        VID = int(VID, 16)
        dict['VID'] = VID

        dict['iSerial'] = sym_list[2]
    except IndexError:
        pass
    return dict


def list_ports_by_vid_pid(vid=None, pid=None):
    """
    Given VID and PID values, searched windows' registry keys for all COMPORTS
    that have the same VID PID values, and returns the intersection of those ports
    with the current ports that are being accessed.

    @param int vid: The vendor id # for a usb device
    @param int vid: The product id # for a usb device
    @return iterator: Ports that are currently active with these VID/PID values
    """
    recorded_ports = []

    try:
      recorded_ports += list(enumerate_recorded_ports_by_vid_pid(vid, pid))
    except Exception as e:
      logging.getLogger('list_ports_windows').error('Error scanning usb devices' + str(e))
      pass

    try:
      recorded_ports += list(enumerate_ftdi_ports_by_vid_pid(vid, pid))
    except Exception as e:
      logging.getLogger('list_ports_windows').error('Error scanning ftdi devices' + str(e))
      pass

    try:
        current_ports = list(enumerate_active_serial_ports())
    except COMPORTAccessError as e:
        # catch exception that is raised if SERIALCOMM does not yet exist.
        # This seems to happen between booting up and plugging in the first serial device. It's not
        # necessarily an error, just indicates that there haven't been any devices plugged in, yet.
        logging.getLogger('list_ports_windows').debug('Could not open COM ports for listing' + str(e))
    else:
        for c_port in current_ports:
            for r_port in recorded_ports:
                # If the COM ports in cur and recoreded ports are the same, we want it
                if 'PortName' in r_port and c_port[1] == r_port['PortName']:
                    try:
                        match_dict = {'iSerial' : r_port['iSerial'],
                                      'VID' : int(r_port['VID'], 16),
                                      'PID' : int(r_port['PID'], 16),
                                      # Windows adds an address, which sees important
                                      # (though it might be totally useless)
                                      'ADDRESS' : c_port[0],
                                      'port' : c_port[1]}
                        # TODO: Find out if addresses do anything
                        yield match_dict
                    except Exception as e:
                        logging.getLogger('list_ports_windows').error('Error scanning usb devices %s' % str(e))



if __name__ == '__main__':
    ports = list_ports_by_vid_pid(int('0x23C1', 16),int('0xD314', 16))
    for port in ports:
        print port
