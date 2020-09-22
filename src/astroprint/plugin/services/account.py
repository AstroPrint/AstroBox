# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import json

from . import PluginService

from astroprint.boxrouter import boxrouterManager
from astroprint.cloud import astroprintCloud, AstroPrintCloudInsufficientPermissionsException
from octoprint.events import eventManager, Events
from octoprint.server import userManager
from octoprint.settings import settings
from octoprint.events import Events

class AccountService(PluginService):
	_validEvents = [
		#watch the state of the user's account: connecting, connected, disconnected , error
		'account_state_change',
		'boxrouter_state_change',
		'fleet_state_change',
		'pin_state_change'
	]

	def __init__(self):
		super(AccountService, self).__init__()
		self._eventManager.subscribe(Events.ASTROPRINT_STATUS, self._onBoxrouterStateChange)
		self._eventManager.subscribe(Events.LOCK_STATUS_CHANGED, self._onAccountStateChange)
		self._eventManager.subscribe(Events.FLEET_STATUS, self._onFleetStateChange)
		self._eventManager.subscribe(Events.PIN_STATUS, self._onPinStateChange)

	def __getLoggedUserEmail(self):
		sets = settings()
		return sets.get(["cloudSlicer", "loggedUser"])

	def __getLoggedUser(self):
		email = self.__getLoggedUserEmail()
		return userManager.findUser(email)

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

			except AstroPrintCloudInsufficientPermissionsException as e:
				self._logger.error("Not enough permissions to login: %s" % json.dumps(e.data))
				if 'org' in e.data and 'in_org' in e.data['org']:
					if e.data['org']['in_org']:
						callback('in_org_no_permissions',True)
					else:
						callback('not_in_org',True)

				else:
					callback('unkonwn_login_error',True)

			except Exception as e:
				self._logger.error("Error Signing into AstroPrint Cloud: %s" % e)
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
		email = password = None

		if 'email' in data:
			email = data['email']

		if 'password' in data:
			password = data['password']

		if email and password:
			try:
				if astroprintCloud().validatePassword(email, password):
					callback('validate_success')
				else:
					callback('invalid_data',True)

			except Exception as e:
				self._logger.error("Error validating passwrod with AstroPrint Cloud: %s" % e)
				callback('astroprint_unrechable',True)

		else:
			self._logger.error('Invalid data received for login')
			callback('invalid_data',True)


	def logout(self, data, callback):
		try:
			astroprintCloud().signout(hasSessionContext= False)
			callback('user successfully logged out')

		except Exception as e:
			self._logger.error('user unsuccessfully logged out: %s' % e , exc_info = True)
			callback('logged_out_unsuccess',True)

	def getStatus(self, callback):
		try:
			user = self.__getLoggedUserEmail()

			payload = {
				'userLogged': user if user else None,
				'boxrouterStatus' :  boxrouterManager().status
			}
			callback(payload)

		except Exception as e:
			self._logger.error('unsuccessfully user status got: %s' %e, exc_info = True)
			callback('getting_status_error')

	def connectBoxrouter(self, callback):
		try:
			boxrouterManager().boxrouter_connect()
			callback('connect_success')
		except Exception as e:
			self._logger.error('boxrouter can not connect: %s' %e, exc_info = True)
			callback('boxrouter_error', True)

	def setPin(self, data, callback):
		try:
			pin = data.get('pin', False)

			if pin is not False: # False means that the parameter is missing. None is a valid value as it would mean to clear it
				user = self.__getLoggedUserEmail()
				if user:
					userManager.changeUserPin(user, pin)
					callback('pin_set')

				else:
					callback('no_user', True)

			else:
				callback('invalid_call', True)

		except Exception as e:
			self._logger.error('Unable to set PIN with: %s' %e, exc_info = True)
			callback('set_pin_error', True)

	def hasPin(self, callback):
		try:
			user = self.__getLoggedUser()
			if user:
				callback(user.has_pin())

			else:
				callback('no_user', True)

		except Exception as e:
			self._logger.error('Error while checking if PIN exists: %s' %e, exc_info = True)
			callback('has_pin_error', True)

	def unblock(self, data, callback):
		try:
			code = data.get('code')

			if code:
				if astroprintCloud().validateUnblockCode(code):
					callback('unblocked')
				else:
					callback('invalid_code', True)

			else:
				callback('invalid_call', True)

		except Exception as e:
			self._logger.error('Unable to unblock controller with: %s' %e, exc_info = True)
			callback('unblock_error', True)

	def validatePin(self, data, callback):
		try:
			pin = data.get('pin')

			if pin:
				user = self.__getLoggedUser()
				if user:
					callback(user.check_pin(pin))

				else:
					callback('no_user', True)

			else:
				callback('invalid_call', True)


		except Exception as e:
			self._logger.error('Error while validating PIN with: %s' %e, exc_info = True)
			callback('validate_pin_error', True)

	def isInFleet(self, data, callback):
		try:
			callback(astroprintCloud().fleetId is not None)

		except Exception as e:
			self._logger.error('Error checking if controller is in fleet: %s' %e, exc_info = True)
			callback('check_infleet_error', True)

	#EVENTS

	def _onAccountStateChange(self,event,value):
		user = self.__getLoggedUserEmail()
		data = {
			'userLogged': user if user else None,
		}
		self.publishEvent('account_state_change',data)

	def _onPinStateChange(self, event, value):
		self.publishEvent('pin_state_change',value)

	def _onBoxrouterStateChange(self,event,value):
			data = {
				'boxrouterStatus' :  boxrouterManager().status
			}
			self.publishEvent('boxrouter_state_change',data)

	def _onFleetStateChange(self,event,value):
			data = {
				'orgId' :  value['orgId'],
				'groupId' :  value['groupId']
			}
			self.publishEvent('fleet_state_change',data)
