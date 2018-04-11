# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com> based on work by Gina Häußge"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from flask_principal import identity_changed, Identity
from tornado.web import StaticFileHandler, HTTPError, RequestHandler, asynchronous
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from flask import url_for, make_response, request, current_app
from flask_login import login_required, login_user, current_user
from werkzeug.utils import redirect
from ext.sockjs.tornado import SockJSConnection
from itsdangerous import base64_decode

import datetime
import stat
import mimetypes
import email
import time
import os
import threading
import logging
import zlib
import json
from functools import wraps

import octoprint.server
import octoprint.util as util

from octoprint.settings import settings
from octoprint.events import Events

from astroprint.boxrouter import boxrouterManager
from astroprint.printfiles import FileDestinations
from astroprint.printfiles.map import SUPPORTED_EXTENSIONS
from astroprint.printer.manager import printerManager
from astroprint.camera import cameraManager
from astroprint.users import ApiUser


def restricted_access(func, apiEnabled=True):
	"""
	If you decorate a view with this, it will ensure that first setup has been
	done for AstroBox's Access Control plus that any conditions of the
	login_required decorator are met. It also allows to login using the masterkey or any
	of the user's apikeys if API access is enabled globally and for the decorated view.

	If AstroBox's Access Control has not been setup yet (indicated by the "firstRun"
	flag from the settings being set to True and the userManager not indicating
	that it's user database has been customized from default), the decorator
	will cause a HTTP 403 status code to be returned by the decorated resource.

	If an API key is provided and it matches a known key, the user will be logged in and
	the view will be called directly. If the provided key doesn't match any known key,
	a HTTP 403 status code will be returned by the decorated resource.

	Otherwise the result of calling login_required will be returned.
	"""
	@wraps(func)
	def decorated_view(*args, **kwargs):
		# if AstroBox hasn't been set up yet, abort
		if settings().getBoolean(["server", "firstRun"]) and (octoprint.server.userManager is None or not octoprint.server.userManager.hasBeenCustomized()):
			return make_response("AstroBox isn't setup yet", 403)

		# if API is globally enabled, enabled for this request and an api key is provided that is not the current UI API key, try to use that
		apikey = getApiKey(request)

		if settings().get(["api", "enabled"]) and apiEnabled and apikey is not None:
			if apikey != octoprint.server.UI_API_KEY:
				if apikey == settings().get(["api", "key"]):
					# master key was used
					user = ApiUser()
				else:
					# user key might have been used
					user = octoprint.server.userManager.findUser(apikey=apikey)

				if user is None:
					return make_response("Invalid API key", 401)

				if login_user(user, remember=False):
					identity_changed.send(current_app._get_current_object(), identity=Identity(user.get_id()))
					return func(*args, **kwargs)

			else:
				return func(*args, **kwargs)

		return make_response("Invalid Api Key or API Disabled", 401)

	return decorated_view


def api_access(func):
	@wraps(func)
	def decorated_view(*args, **kwargs):
		if not settings().get(["api", "enabled"]):
			make_response("API disabled", 401)
		apikey = getApiKey(request)
		if apikey is None:
			make_response("No API key provided", 401)
		if apikey != settings().get(["api", "key"]):
			make_response("Invalid API key", 403)
		return func(*args, **kwargs)
	return decorated_view


def getUserForApiKey(apikey):
	if settings().get(["api", "enabled"]) and apikey is not None:
		if apikey == settings().get(["api", "key"]):
			# master key was used
			return ApiUser()
		else:
			# user key might have been used
			return octoprint.server.userManager.findUser(apikey=apikey)
	else:
		return None


def getApiKey(request):
	# Check Flask GET/POST arguments
	if hasattr(request, "values") and "apikey" in request.values:
		return request.values["apikey"]

	# Check Tornado GET/POST arguments
	if hasattr(request, "arguments") and "apikey" in request.arguments and len(request.arguments["apikey"].strip()) > 0:
		return request.arguments["apikey"]

	# Check Tornado and Flask headers
	if "X-Api-Key" in request.headers.keys():
		return request.headers.get("X-Api-Key")

	return None


#~~ Printer state


class PrinterStateConnection(SockJSConnection):
	EVENTS = [Events.UPDATED_FILES, Events.METADATA_ANALYSIS_FINISHED, Events.SLICING_STARTED, Events.SLICING_DONE, Events.SLICING_FAILED,
				Events.TRANSFER_STARTED, Events.TRANSFER_DONE, Events.CLOUD_DOWNLOAD, Events.ASTROPRINT_STATUS, Events.SOFTWARE_UPDATE,
				Events.CAPTURE_INFO_CHANGED, Events.LOCK_STATUS_CHANGED, Events.NETWORK_STATUS, Events.INTERNET_CONNECTING_STATUS,
				Events.GSTREAMER_EVENT, Events.TOOL_CHANGE, Events.COPY_TO_HOME_PROGRESS, Events.EXTERNAL_DRIVE_MOUNTED,
				Events.EXTERNAL_DRIVE_EJECTED, Events.EXTERNAL_DRIVE_PHISICALLY_REMOVED]

	def __init__(self, userManager, eventManager, session):
		SockJSConnection.__init__(self, session)

		self._logger = logging.getLogger(__name__)

		self._temperatureBacklog = []
		self._temperatureBacklogMutex = threading.Lock()
		self._emitLock = threading.Lock()

		self._userManager = userManager
		self._eventManager = eventManager

	def _getRemoteAddress(self, request):
		forwardedFor = request.headers.get("X-Forwarded-For")
		if forwardedFor is not None:
			return forwardedFor.split(",")[0]
		return request.ip

	def on_open(self, request):
		s = settings()
		loggedUsername = s.get(["cloudSlicer", "loggedUser"])

		if loggedUsername:
			token = request.arguments.get("token")
			token = token[0] if token else None
			tokenContents = octoprint.server.read_ws_token(token)
			if not tokenContents or tokenContents['public_key'] != self._userManager.findUser(loggedUsername).publicKey:
				return False

		remoteAddress = self._getRemoteAddress(request)
		self._logger.info("New connection from client [IP address: %s, Session id: %s]", remoteAddress, self.session.session_id)

		# connected => update the API key, might be necessary if the client was left open while the server restarted
		self._emit("connected", {"apikey": octoprint.server.UI_API_KEY, "version": octoprint.server.VERSION, "sessionId": self.session.session_id})
		self.sendEvent(Events.ASTROPRINT_STATUS, boxrouterManager().status)

		printer = printerManager()

		printer.registerCallback(self)
		printer.fileManager.registerCallback(self)

		self._eventManager.fire(Events.CLIENT_OPENED, {"remoteAddress": remoteAddress})
		for event in PrinterStateConnection.EVENTS:
			self._eventManager.subscribe(event, self._onEvent)

	def on_close(self):
		self._logger.info("Client connection closed [Session id: %s]", self.session.session_id)

		printer = printerManager()

		printer.unregisterCallback(self)
		printer.fileManager.unregisterCallback(self)
		cameraManager().closeLocalVideoSession(self.session.session_id)

		self._eventManager.fire(Events.CLIENT_CLOSED)
		for event in PrinterStateConnection.EVENTS:
			self._eventManager.unsubscribe(event, self._onEvent)

	def on_message(self, message):
		pass

	def sendCurrentData(self, data):
		# add current temperature, log and message backlogs to sent data
		with self._temperatureBacklogMutex:
			temperatures = self._temperatureBacklog
			self._temperatureBacklog = []

		data.update({
			"temps": temperatures
		})
		self._emit("current", data)

	def sendHistoryData(self, data):
		pass

	def sendCommsData(self, direction, data):
		self._emit('commsData', {
			'direction': direction,
			'data': data
		})

	def sendEvent(self, type, payload=None):
		self._emit("event", {"type": type, "payload": payload})

	def sendFeedbackCommandOutput(self, name, output):
		self._emit("feedbackCommandOutput", {"name": name, "output": output})

	def sendTimelapseConfig(self, timelapseConfig):
		self._emit("timelapse", timelapseConfig)

	def addTemperature(self, data):
		with self._temperatureBacklogMutex:
			self._temperatureBacklog.append(data)

	def _onEvent(self, event, payload):
		self.sendEvent(event, payload)

	def _emit(self, type, payload):
		with self._emitLock:
			self.send({type: payload})


#~~ customized large response handler


class LargeResponseHandler(StaticFileHandler):

	CHUNK_SIZE = 16 * 1024

	def initialize(self, path, default_filename=None, as_attachment=False, access_validation=None):
		StaticFileHandler.initialize(self, path, default_filename)
		self._as_attachment = as_attachment
		self._access_validation = access_validation

	def get(self, path, include_body=True):
		if self._access_validation is not None:
			self._access_validation(self.request)

		path = self.parse_url_path(path)
		abspath = os.path.abspath(os.path.join(self.root, path))
		# os.path.abspath strips a trailing /
		# it needs to be temporarily added back for requests to root/
		if not (abspath + os.path.sep).startswith(self.root):
			raise HTTPError(403, "%s is not in root static directory", path)
		if os.path.isdir(abspath) and self.default_filename is not None:
			# need to look at the request.path here for when path is empty
			# but there is some prefix to the path that was already
			# trimmed by the routing
			if not self.request.path.endswith("/"):
				self.redirect(self.request.path + "/")
				return
			abspath = os.path.join(abspath, self.default_filename)
		if not os.path.exists(abspath):
			raise HTTPError(404)
		if not os.path.isfile(abspath):
			raise HTTPError(403, "%s is not a file", path)

		stat_result = os.stat(abspath)
		modified = datetime.datetime.fromtimestamp(stat_result[stat.ST_MTIME])

		self.set_header("Last-Modified", modified)

		mime_type, encoding = mimetypes.guess_type(abspath)
		if mime_type:
			self.set_header("Content-Type", mime_type)

		cache_time = self.get_cache_time(path, modified, mime_type)

		if cache_time > 0:
			self.set_header("Expires", datetime.datetime.utcnow() +
										 datetime.timedelta(seconds=cache_time))
			self.set_header("Cache-Control", "max-age=" + str(cache_time))

		self.set_extra_headers(path)

		# Check the If-Modified-Since, and don't send the result if the
		# content has not been modified
		ims_value = self.request.headers.get("If-Modified-Since")
		if ims_value is not None:
			date_tuple = email.utils.parsedate(ims_value)
			if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
			if if_since >= modified:
				self.set_status(304)
				return

		if not include_body:
			assert self.request.method == "HEAD"
			self.set_header("Content-Length", stat_result[stat.ST_SIZE])
		else:
			with open(abspath, "rb") as file:
				while True:
					data = file.read(LargeResponseHandler.CHUNK_SIZE)
					if not data:
						break
					self.write(data)
					self.flush()

	def set_extra_headers(self, path):
		if self._as_attachment:
			self.set_header("Content-Disposition", "attachment")


##~~ URL Forward Handler for forwarding requests to a preconfigured static URL


class UrlForwardHandler(RequestHandler):

	def initialize(self, url=None, as_attachment=False, basename=None, access_validation=None):
		RequestHandler.initialize(self)
		self._url = url
		self._as_attachment = as_attachment
		self._basename = basename
		self._access_validation = access_validation

	@asynchronous
	def get(self, *args, **kwargs):
		if self._access_validation is not None:
			self._access_validation(self.request)

		if self._url is None:
			raise HTTPError(404)

		client = AsyncHTTPClient()
		r = HTTPRequest(url=self._url, method=self.request.method, body=self.request.body, headers=self.request.headers, follow_redirects=False, allow_nonstandard_methods=True)

		try:
			return client.fetch(r, self.handle_response)
		except HTTPError as e:
			if hasattr(e, "response") and e.response:
				self.handle_response(e.response)
			else:
				raise HTTPError(500)

	def handle_response(self, response):
		if response.error and not isinstance(response.error, HTTPError):
			raise HTTPError(500)

		filename = None

		self.set_status(response.code)
		for name in ("Date", "Cache-Control", "Server", "Content-Type", "Location"):
			value = response.headers.get(name)
			if value:
				self.set_header(name, value)

				if name == "Content-Type":
					filename = self.get_filename(value)

		if self._as_attachment:
			if filename is not None:
				self.set_header("Content-Disposition", "attachment; filename=%s" % filename)
			else:
				self.set_header("Content-Disposition", "attachment")

		if response.body:
			self.write(response.body)
		self.finish()

	def get_filename(self, content_type):
		if not self._basename:
			return None

		typeValue = map(str.strip, content_type.split(";"))
		if len(typeValue) == 0:
			return None

		extension = mimetypes.guess_extension(typeValue[0])
		if not extension:
			return None

		return "%s%s" % (self._basename, extension)


#~~ admin access validator for use with tornado


def admin_validator(request):
	"""
	Validates that the given request is made by an admin user, identified either by API key or existing Flask
	session.

	Must be executed in an existing Flask request context!

	:param request: The Flask request object
	"""

	apikey = getApiKey(request)
	if settings().get(["api", "enabled"]) and apikey is not None:
		user = getUserForApiKey(apikey)
	else:
		user = current_user

	if user is None or not user.is_authenticated or not user.is_admin():
		raise HTTPError(403)


#~~ user access validator for use with tornado


def user_validator(request):
	"""
	Validates that the given request is made by an authenticated user, identified either by API key or existing Flask
	session.

	Must be executed in an existing Flask request context!

	:param request: The Flask request object
	"""

	apikey = getApiKey(request)
	if settings().get(["api", "enabled"]) and apikey is not None:
		user = getUserForApiKey(apikey)
	else:
		user = current_user

	if user is None or not user.is_authenticated:
		raise HTTPError(403)


#~~ reverse proxy compatible wsgi middleware


class ReverseProxied(object):
	"""
	Wrap the application in this middleware and configure the
	front-end server to add these headers, to let you quietly bind
	this to a URL other than / and to an HTTP scheme that is
	different than what is used locally.

	In nginx:
		location /myprefix {
			proxy_pass http://192.168.0.1:5001;
			proxy_set_header Host $host;
			proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header X-Scheme $scheme;
			proxy_set_header X-Script-Name /myprefix;
		}

	Alternatively define prefix and scheme via config.yaml:
		server:
			baseUrl: /myprefix
			scheme: http

	:param app: the WSGI application
	"""

	def __init__(self, app):
		self.app = app

	def __call__(self, environ, start_response):
		script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
		if not script_name:
			script_name = settings().get(["server", "baseUrl"])

		if script_name:
			environ['SCRIPT_NAME'] = script_name
			path_info = environ['PATH_INFO']
			if path_info.startswith(script_name):
				environ['PATH_INFO'] = path_info[len(script_name):]

		scheme = environ.get('HTTP_X_SCHEME', '')
		if not scheme:
			scheme = settings().get(["server", "scheme"])

		if scheme:
			environ['wsgi.url_scheme'] = scheme
		return self.app(environ, start_response)


def redirectToTornado(request, target):
	requestUrl = request.url
	appBaseUrl = requestUrl[:requestUrl.find(url_for("index") + "api")]

	redirectUrl = appBaseUrl + target
	if "?" in requestUrl:
		fragment = requestUrl[requestUrl.rfind("?"):]
		redirectUrl += fragment
	return redirect(redirectUrl)
