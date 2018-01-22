# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events

class AuthService(PluginService):
	_validEvents = []

	def __init__(self):
		super(AuthService, self).__init__()

	#REQUESTS

	def getAccessKeys(self, data, sendResponse):

		publicKey = email = accessKey = None

		if 'email' in data:
			email = data['email']

		if 'accessKey' in data:
			accessKey = data['accessKey']

		userLogged = settings().get(["cloudSlicer", "loggedUser"])
		####
		# - nobody logged: None
		# - any log: email

		if email and accessKey:#somebody is logged in the remote client
			if userLogged:#Somebody logged in Astrobox
				if userLogged == email:#I am the user logged
					online = networkManager().isOnline()

					if online:
						publicKey = astroprintCloud().get_public_key(email, accessKey)

						if not publicKey:
							self._logger.error('error getting public key', exc_info = True)
							sendResponse('error_getting_public_key',True)
							return

					else:
						user = userManager.findUser(email)
						if user.get_private_key() != accessKey:
							self._logger.error('incorrect logged user', exc_info = True)
							sendResponse('incorrect_logged_user',True)
							return

				else:#I am NOT the logged user
					self._logger.error('incorrect logged user', exc_info = True)
					sendResponse('incorrect_logged_user',True)
					return

		else:#nodody is logged in the remote client
			if userLogged:
				self._logger.error('any user logged', exc_info = True)
				sendResponse('no_user_logged',True)
				return

		sendResponse({
			'api_key': UI_API_KEY,
			'ws_token': create_ws_token(publicKey)
		})
