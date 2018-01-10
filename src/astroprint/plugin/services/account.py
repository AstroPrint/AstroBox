# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from astroprint.boxrouter import boxrouterManager
from astroprint.cloud import astroprintCloud
from octoprint.events import eventManager, Events
from octoprint.server import userManager
from octoprint.settings import settings
from octoprint.events import Events

class AccountService(PluginService):
	_validEvents = [
		#watch the state of the user's account: connecting, connected, disconnected , error
		'account_state_change'
	]

	def __init__(self):
		super(AccountService, self).__init__()
		self._eventManager.subscribe(Events.ASTROPRINT_STATUS, self._onAccountStateChange)

	#REQUESTS

	def login(self, data,callback):
		email = private_key = password = None

		if 'email' in data:
			email = data['email']

		if 'password' in data:
			password = data['password']

		if 'private_key' in data:
			private_key = data['private_key']

		if email and password:
			try:
				if astroprintCloud().signin(email, password, hasSessionContext= False):
					callback('login_success')

			except Exception as e:
				self._logger.error("AstroPrint.com can't be reached " + e.args[0])
				callback('astroprint_unrechable',True)

		elif email and private_key:
			try:
				if astroprintCloud().signinWithKey(email, private_key, hasSessionContext= False):
						callback('login_success')

			except Exception as e:
				self._logger.error('user unsuccessfully logged in',exc_info = True)
				callback('no_login',True)

		else:
			self._logger.error('Invalid data received for login')
			callback('invalid_data',True)

	def validate(self, data, callback):
		email = private_key = password = None

		if 'email' in data:
			email = data['email']

		if 'password' in data:
			password = data['password']

		if email and password:
			try:
				if astroprintCloud().validatePassword(email, password):
					callback('validate_success')

			except Exception as e:
				self._logger.error("AstroPrint.com can't be reached " + e.args[0])
				callback('astroprint_unrechable',True)

		else:
			self._logger.error('Invalid data received for login')
			callback('invalid_data',True)


	def logout(self, data, callback):
		try:
			astroprintCloud().signout(hasSessionContext= False)
			callback('user successfully logged out')

		except Exception as e:
			self._logger.error('user unsuccessfully logged out', exc_info = True)
			callback('logged_out_unsuccess',True)

	def getStatus(self, callback):
		try:
			sets = settings()
			payload = {
				'state':  "connected" if  sets.get(["cloudSlicer", "loggedUser"]) else "disconnected",
				'boxrouterStatus' :  boxrouterManager().status
			}
			if sets.get(["cloudSlicer", "loggedUser"]):
				payload['user'] = sets.get(["cloudSlicer", "loggedUser"])

			callback({
				'astroprint-status': payload
			})

		except Exception as e:
			self._logger.error('unsuccessfully user status got', exc_info = True)
			callback('getting_status_error')


	#EVENTS

	def _onAccountStateChange(self,event,value):
			sets = settings()
			data = {
				'state': value if value == "connected" or value == "connecting" else "connected" if  sets.get(["cloudSlicer", "loggedUser"]) else "disconnected"
			}
			if sets.get(["cloudSlicer", "loggedUser"]):
				data['user'] = sets.get(["cloudSlicer", "loggedUser"])

			self.publishEvent('account_state_change',data)
