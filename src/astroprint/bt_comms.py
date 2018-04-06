__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import threading
import json
import subprocess
import time

from bluetooth import BluetoothSocket, L2CAP, BluetoothError
from netifaces import interfaces, ifaddresses, AF_INET
from sys import platform
from astroprint.network.manager import networkManager

# singleton
_instance = None

def bluetoothCommsManager():
	global _instance

	if _instance is None:
		if platform.startswith("linux"):
			_instance = BluetoothCommsManager()

		elif platform == "darwin":
			_instance = BluetoothCommsManager()
			logger = logging.getLogger(__name__)
			logger.info('darwin platform is not able to enable bluetooth communications...')

	return _instance

#
# Thread for bluetooth communications
#
class BluetoothCommsManager(threading.Thread):
	def __init__(self):
		super(BluetoothCommsManager, self).__init__()
		self.daemon = True
		self._logger = logging.getLogger(__name__)

		if self._isBTAvailable():
			self.isBTAvailable = True
			self.server_sock = BluetoothSocket( L2CAP )
			self.client_sock = None
			self.client_addr = None
			self.port = 0x1001
			self.BTProcess = None

		else :
			self.isBTAvailable = False
			self.BTProcess = None


	def _isBTAvailable(self):

		args = ['hciconfig', 'hci0']

		try:
			BTAv = subprocess.Popen(
				args,
				stdout=subprocess.PIPE
			)

			line = BTAv.stdout.readline()

			if line and 'No such device' in line:
				return False
			else:
				return True

		except Exception, error:
			self._logger.error(error)
			return False


	def isBTON(self):
		return self.BTProcess and self.BTProcess.returncode is None

	def turnBTOn(self):

		info = ""

		#Bluetooth Device ON
		if self.isBTON():
			info = 'Bluetooth Device was already running'
			self._logger.info('Bluetooth Device was already running')
			return {
				'status': True,
				'info': info
			}

		args = ['hciconfig', 'hci0', 'up', 'piscan']

		try:
			self.BTProcess = subprocess.Popen(
				args,
				stdout=subprocess.PIPE
			)

		except Exception, error:
			info = "Error turning ON Bluetooth Device: %s" % str(error)
			self._logger.error(info)
			self.BTProcess = None

		time.sleep(1)

		if self.BTProcess:

			info = 'Bluetooth Device ON'

			args = ['hciconfig', 'hci0', 'name']

			try:
				BTname = subprocess.Popen(
					args,
					stdout=subprocess.PIPE
				)

				self._logger.info('Bluetooth Device ON. Info:')
				for line in iter(BTname.stdout.readline,''):
					self._logger.info((line.lstrip()).rstrip())

			except Exception, error:
				BTname = None
				self._logger.info(info)

			return {
				'status': True,
				'info': info
			}

		return {
			'status': False,
			'info': info
		}

	def turnBTOff(self):
		self._logger.info('turnBTOff')

		#Bluetooth Device OFF
		if self.BTProcess:

			info = ''

			args = ['hciconfig', 'hci0', 'down']

			try:
				BTOffProcess = subprocess.Popen(
					args,
					stdout=subprocess.PIPE
				)

			except Exception, error:
				info = "Error turning OFF Bluetooth Device: %s" % str(error)
				self._logger.error(info)
				BTOffProcess = None

			if BTOffProcess:

				info = 'Bluetooth Device OFF'

				self.BTProcess = None

				self._logger.info(info)

				return {
					'status': True,
					'info': info
				}

			return {
				'status': False,
				'info': info
			}

		else:
			#Bluetooth Device already OFF
			return {
				'status': True,
				'info': 'Bluetooth Device was already stopped'
			}


	def run(self):

		if self.isBTAvailable:

			self.server_sock.bind(("",self.port))
			self.server_sock.listen(1)

			self.newConnection()

	def newConnection(self):

		try:

			self.client_sock,self.client_addr = self.server_sock.accept()
			self._logger.info("Accepted bluetooth connection from " + self.client_addr[0])

			self.dataRecv = self.client_sock.recv(1024)

			self.parseMessage(self.dataRecv)

			while self.dataRecv:
				self.dataRecv = self.client_sock.recv(1024)
				self.parseMessage(self.dataRecv)

		except BluetoothError as e:

			self._logger.error('connection error occurred...')

			t = eval(e[0])

			if 103 in t:
				self._logger.error('AstroBox ' + t[1])

	def parseMessage(self,data):

		try:

			message = json.loads(str(data),encoding='utf8')

			if 'action' in message:

				## WIFILIST ##
				if message['action'] == 'wifilist':

					networks = networkManager().getWifiNetworks()

					if networks:
						self.sendMessage(self.composeMessage('wifilist',networks))
						return
					else:
						self.sendMessage(self.composeMessage("wifilist",None,True))
						return

				## CONNECT_WIFI ##
				elif message['action'] == 'connect_wifi':

					if 'id' in message and 'password' in message:
						result = networkManager().setWifiNetwork(message['id'], message['password'])

						if result:

							addresses = {}

							not_ready = True

							while not_ready:

								addresses = {}

								time.sleep(0.5)

								for ifaceName in interfaces():
									addrs = [i['addr'] for i in ifaddresses(ifaceName).setdefault(AF_INET, [{'addr':None}] )]
									addresses[ifaceName] = addrs

								not_ready = not ('wlan0' in addresses and addresses['wlan0'][0] is not None)

							del addresses['lo']

							result['ip'] = addresses

							self.sendMessage(self.composeMessage('connect_wifi',result))
							return
						else:
							self.sendMessage(self.composeMessage('connect_wifi','network_not_found',True))
							return

					self.sendMessage('incorrect_data',True)


				## DISCONNECT ##
				elif message['action'] == 'disconnect':
					self.sendMessage(self.composeMessage('disconnect','will_be_disconnected'))
					self.dataRecv = None
					self.client_sock.close()
					self.client_sock = None
					self.newConnection()

				else:
					self.sendMessage(self.composeMessage(message['action'],'invalid_message',True))

		except Exception as e:
			self.sendMessage(self.composeMessage('fail','wrong bluetooth message received',True))
			self._logger.error('wrong bluetooth message received')
			self._logger.error(e)


	def composeMessage(self, key, message, error = False):
		messageToReturn = {}

		messageToReturn['key'] = key

		if error:
			messageToReturn['error'] = True

		messageToReturn['message'] = message

		return messageToReturn

	def sendMessage(self,message):
		try:
			self.client_sock.send(json.dumps(message))

		except BluetoothError as e:

			self._logger.error('error occurred while sending message to client ' + self.client_addr[0])

			t = eval(e[0])

			if 107 in t:
				self._logger.error('client ' + self.client_addr[0] + ' was down...')

			self.dataRecv = None
			self.client_sock.close()
			self.client_sock = None
			self.newConnection()

	def shutdown(self):
		self._logger.info('Shutting Down BluetoothCommsManager')

		self.turnBTOff()

		if self.client_sock:
			self.client_sock.close()

		self.server_sock.close()

		global _instance
		_instance = None

		return True
