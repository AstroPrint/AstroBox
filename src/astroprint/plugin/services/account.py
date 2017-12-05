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

		if 'private_key' in data:
			private_key = data['private_key']

		if email and private_key:
			try:
				user = userManager.findUser(email)

				if not user:
					public_key = astroprintCloud().get_public_key(email, private_key)
					user = userManager.addUser(email, '', public_key, private_key, True)

				#login_user(user, remember=True)
				userId = user.get_id()

				sets = settings()

				sets.set(["cloudSlicer", "loggedUser"], userId)
				sets.save()

				boxrouterManager().boxrouter_connect()

				eventManager().fire(Events.LOCK_STATUS_CHANGED, userId)

				callback('logging_success')

			except Exception as e:
				self._logger.error('user unsuccessfully logged in',exc_info = True)
				callback('no_login',True)

		else:

			if 'password' in data:
				password = data['password']

			if email and password:
				try:
					if astroprintCloud().signin(email, password):
						callback('logging_success')

				except Exception as e:
					self._logger.error("AstroPrint.com can't be reached " + e.args[0])
					callback('astroprint_unrechable',True)

			else:
				self._logger.error('Invalid data received for loging')
				callback('invalid_data',True)

	def logout(self, data, callback):
		try:

			#astroprintCloud().signout()
			astroprintCloud().remove_logged_user()
			callback('user successfully logged out')

		except Exception as e:
			self._logger.error('user unsuccessfully logged out', exc_info = True)
			callback('logged_out_unsuccess',True)

	def getStatus(self, callback):
		try:

			payload = {
				'state': boxrouterManager().status,
			}
			if boxrouterManager().status == "connected":
				sets = settings()
				payload['user'] = sets.get(["cloudSlicer", "loggedUser"])

			callback({
				'astroprint-status': payload
			})

		except Exception as e:
			self._logger.error('unsuccessfully user status got', exc_info = True)
			callback('getting_status_error')


	#EVENTS

	def _onAccountStateChange(self,event,value):
			print 'onAccountStateChange'
			data = {"state" : value}
			if value == "connected":
				sets = settings()
				data['user'] = sets.get(["cloudSlicer", "loggedUser"])
			print data
			self.publishEvent('account_state_change',data)
