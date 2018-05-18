# coding=utf-8
from octoprint.server.util import getApiKey, getUserForApiKey

__author__ = "AstroPrint Product Team <product@3dagogo.com> based on the work by Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import netaddr
import sarge
import threading
import time

from flask import Blueprint, request, jsonify, abort, current_app, session, make_response
from flask_login import login_user, logout_user, current_user
from flask_principal import Identity, identity_changed, AnonymousIdentity

import octoprint.util as util
import octoprint.server
from octoprint.server import restricted_access, admin_permission, NO_CONTENT, UI_API_KEY, OK
from octoprint.settings import settings as s, valid_boolean_trues

#import astroprint.users

#~~ init api blueprint, including sub modules

api = Blueprint("api", __name__)

from . import job as api_job
#from . import files as api_files
#from . import settings as api_settings
#from . import timelapse as api_timelapse
#from . import users as api_users
#from . import log as api_logs
from astroprint.api import settings as api_settings
from astroprint.api import setup as api_astroprint_setup
from astroprint.api import boxrouter as api_astroprint_boxrouter
from astroprint.api import cloud as api_astroprint_cloud
from astroprint.api import camera as api_astroprint_camera
from astroprint.api import printerprofile as api_astroprint_printerprofile
from astroprint.api import additionaltasks as api_astroprint_additionaltasks
from astroprint.api import maintenancemenu as api_astroprint_maintenancemenu
from astroprint.api import printer as api_astroprint_printer
from astroprint.api import connection as api_astroprint_connection
from astroprint.api import files as api_astroprint_files
from astroprint.cloud import astroprintCloud, AstroPrintCloudNoConnectionException
from requests import ConnectionError



VERSION = "1.0"

def optionsAllowOrigin(request):
	""" Always reply 200 on OPTIONS request """

	resp = current_app.make_default_options_response()

	# Allow the origin which made the XHR
	resp.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
	# Allow the actual method
	resp.headers['Access-Control-Allow-Methods'] = request.headers['Access-Control-Request-Method']
	# Allow for 10 seconds
	resp.headers['Access-Control-Max-Age'] = "10"

	# 'preflight' request contains the non-standard headers the real request will have (like X-Api-Key)
	customRequestHeaders = request.headers.get('Access-Control-Request-Headers', None)
	if customRequestHeaders is not None:
		# If present => allow them all
		resp.headers['Access-Control-Allow-Headers'] = customRequestHeaders

	return resp

@api.before_request
def beforeApiRequests():
	"""
	All requests in this blueprint need to be made supplying an API key. This may be the UI_API_KEY, in which case
	the underlying request processing will directly take place, or it may be the global or a user specific case. In any
	case it has to be present and must be valid, so anything other than the above three types will result in denying
	the request.
	"""

	if request.method == 'OPTIONS' and s().getBoolean(["api", "allowCrossOrigin"]):
		return optionsAllowOrigin(request)

	apikey = getApiKey(request)
	if apikey is None:
		# no api key => 401
		return make_response("No API key provided", 401)

	if apikey == UI_API_KEY:
		# ui api key => continue regular request processing
		return

	if not s().get(["api", "enabled"]):
		# api disabled => 401
		return make_response("API disabled", 401)

	if apikey == s().get(["api", "key"]):
		# global api key => continue regular request processing
		return

	user = getUserForApiKey(apikey)
	if user is not None:
		# user specific api key => continue regular request processing
		return

	# invalid api key => 401
	return make_response("Invalid API key", 401)

@api.after_request
def afterApiRequests(resp):

	# Allow crossdomain
	allowCrossOrigin = s().getBoolean(["api", "allowCrossOrigin"])
	if request.method != 'OPTIONS' and 'Origin' in request.headers and allowCrossOrigin:
		resp.headers['Access-Control-Allow-Origin'] = request.headers['Origin']

	return resp


#~~ first run setup


# @api.route("/setup", methods=["POST"])
# def firstRunSetup():
# 	if not s().getBoolean(["server", "firstRun"]):
# 		abort(403)

# 	if "ac" in request.values.keys() and request.values["ac"] in valid_boolean_trues and \
# 					"user" in request.values.keys() and "pass1" in request.values.keys() and \
# 					"pass2" in request.values.keys() and request.values["pass1"] == request.values["pass2"]:
# 		# configure access control
# 		s().setBoolean(["accessControl", "enabled"], True)
# 		octoprint.server.userManager.addUser(request.values["user"], request.values["pass1"], True, ["user", "admin"])
# 		s().setBoolean(["server", "firstRun"], False)
# 	elif "ac" in request.values.keys() and not request.values["ac"] in valid_boolean_trues:
# 		# disable access control
# 		s().setBoolean(["accessControl", "enabled"], False)
# 		s().setBoolean(["server", "firstRun"], False)

# 		octoprint.server.loginManager.anonymous_user = astroprint.users.DummyUser
# 		octoprint.server.principals.identity_loaders.appendleft(astroprint.users.dummy_identity_loader)

# 	s().save()
# 	return NO_CONTENT

#~~ system state


@api.route("/state", methods=["GET"])
@restricted_access
def apiPrinterState():
	return make_response(("/api/state has been deprecated, use /api/printer instead", 405, []))


@api.route("/version", methods=["GET"])
@restricted_access
def apiVersion():
	return jsonify({
		"server": octoprint.server.VERSION,
		"api": octoprint.server.api.VERSION
	})

#~~ system control


@api.route("/system", methods=["POST"])
#@restricted_access
#@admin_permission.require(403)
def performSystemAction():
	if "action" in request.values.keys():
		action = request.values["action"]
		available_actions = s().get(["system", "actions"])
		logger = logging.getLogger(__name__)

		for availableAction in available_actions:
			if availableAction["action"] == action:
				command = availableAction["command"]
				if command:
					logger.info("Performing command: %s" % command)

					def executeCommand(command, logger):
						time.sleep(0.5) #add a small delay to make sure the response is sent
						try:
							p = sarge.run(command, stderr=sarge.Capture())
							if p.returncode != 0:
								returncode = p.returncode
								stderr_text = p.stderr.text
								logger.warn("Command failed with return code %i: %s" % (returncode, stderr_text))
							else:
								logger.info("Command executed sucessfully")

						except Exception, e:
							logger.warn("Command failed: %s" % e)

					executeThread = threading.Thread(target=executeCommand, args=(command, logger))
					executeThread.start()

					return OK

				else:
					logger.warn("Action %s is misconfigured" % action)
					return ("Misconfigured action", 500)

		logger.warn("No suitable action in config for: %s" % action)
		return ("Command not found", 404)

	else:
		return ("Invalid data", 400)


#~~ Login/user handling
@api.route("/login", methods=["POST"])
def login():
	if octoprint.server.userManager is not None and "user" in request.values.keys() and "pass" in request.values.keys():
		username = request.values["user"]
		password = request.values["pass"]

		if "remember" in request.values.keys() and request.values["remember"] == "true":
			remember = True
		else:
			remember = False

		user = octoprint.server.userManager.findUser(username)
		if user is not None:
			if user.has_password():
				if astroprintCloud().validatePassword(username, password):
					login_user(user, remember=remember)
					identity_changed.send(current_app._get_current_object(), identity=Identity(user.get_id()))
					return jsonify(user.asDict())
			else :
				try:
					if astroprintCloud().signin(username, password):
						return jsonify(current_user)

				except (AstroPrintCloudNoConnectionException, ConnectionError):
					return make_response(("AstroPrint.com can't be reached", 503, []))
		return make_response(("User unknown or password incorrect", 401, []))
	elif "passive" in request.values.keys():
		user = current_user
		if user is not None and not user.is_anonymous:
			identity_changed.send(current_app._get_current_object(), identity=Identity(user.get_id()))
			return jsonify(user.asDict())
		elif s().getBoolean(["accessControl", "autologinLocal"]) \
			and s().get(["accessControl", "autologinAs"]) is not None \
			and s().get(["accessControl", "localNetworks"]) is not None:

			autologinAs = s().get(["accessControl", "autologinAs"])
			localNetworks = netaddr.IPSet([])
			for ip in s().get(["accessControl", "localNetworks"]):
				localNetworks.add(ip)

			try:
				remoteAddr = util.getRemoteAddress(request)
				if netaddr.IPAddress(remoteAddr) in localNetworks:
					user = octoprint.server.userManager.findUser(autologinAs)
					if user is not None:
						login_user(user)
						identity_changed.send(current_app._get_current_object(), identity=Identity(user.get_id()))
						return jsonify(user.asDict())
			except:
				logger = logging.getLogger(__name__)
				logger.exception("Could not autologin user %s for networks %r" % (autologinAs, localNetworks))
	return NO_CONTENT


@api.route("/logout", methods=["POST"])
@restricted_access
def logout():
	# Remove session keys set by Flask-Principal
	for key in ('identity.id', 'identity.auth_type'):
		del session[key]
	identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())

	logout_user()

	return NO_CONTENT
