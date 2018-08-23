# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com> based on work by Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import Queue
import threading
import yaml
import time
import octoprint.util as util

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from werkzeug.utils import secure_filename

class FileDestinations(object):
	SDCARD = "sdcard"
	LOCAL = "local"

class FileTypes(object):
	STL = "stl"
	GCODE = "gcode"
	X3G = "x3g"

class PrintFilesManager(object):
	name = None
	fileFormat = None
	SUPPORTED_EXTENSIONS = []
	SUPPORTED_DESIGN_EXTENSIONS = ["stl"]

	def __init__(self):

		self._settings = settings()

		self._uploadFolder = self._settings.getBaseFolder("uploads")

		self._callbacks = []

		self._metadata = {}
		self._metadataDirty = False
		self._metadataFile = os.path.join(self._uploadFolder, "metadata.yaml")
		self._metadataTempFile = os.path.join(self._uploadFolder, "metadata.yaml.tmp")
		self._metadataFileAccessMutex = threading.Lock()

		self._loadMetadata(migrate=True)
		self._processAnalysisBacklog()

	def rampdown(self):
		del self._callbacks
		self._metadataAnalyzer.stop()
		self._metadataAnalyzer._worker.join()

	def isValidFilename(self, filename):
		return "." in filename and filename.rsplit(".", 1)[1].lower() in self.SUPPORTED_EXTENSIONS

	def isDesignFileName(self, filename):
		return "." in filename and filename.rsplit(".", 1)[1].lower() in self.SUPPORTED_DESIGN_EXTENSIONS

	def _processAnalysisBacklog(self):
		for osFile in os.listdir(self._uploadFolder):
			filename = self._getBasicFilename(osFile)
			if not self.isValidFilename(filename):
				continue

			absolutePath = self.getAbsolutePath(filename)
			if absolutePath is None:
				continue

			fileData = self.getFileData(filename)
			if fileData is not None and "gcodeAnalysis" in fileData:
				continue

			self._metadataAnalyzer.addFileToBacklog(filename)

	def _onMetadataAnalysisFinished(self, filename, results):

		if filename is None or results is None:
			return

		basename = os.path.basename(filename)

		absolutePath = self.getAbsolutePath(basename)
		if absolutePath is None:
			return

		analysisResult = {}
		dirty = False
		if results.totalMoveTimeMinute:
			analysisResult["print_time"] = results.totalMoveTimeMinute * 60
			dirty = True
		if results.extrusionAmount:
			analysisResult["filament"] = {}
			totalVolume = 0
			totalLength = 0
			for i in range(len(results.extrusionAmount)):
				analysisResult["filament"]["tool%d" % i] = {
					"length": results.extrusionAmount[i],
					"volume": results.extrusionVolume[i]
				}
				totalVolume += results.extrusionVolume[i]
				totalLength += results.extrusionAmount[i]
			dirty = True

			analysisResult['filament_volume'] = totalVolume
			analysisResult['filament_length'] = totalLength


		try:

			if results.layerCount:
				analysisResult['layer_count'] = results.layerCount
				dirty = True
		except: pass

		try:
			if results.size:
				mapSize = {}
				mapSize['x'] = results.size['x']
				mapSize['y'] = results.size['y']
				mapSize['z'] = results.size['z']

				analysisResult['size'] = mapSize
				dirty = True
		except: pass

		try:
			if results.layer_height:
				analysisResult['layer_height'] = results.layer_height
				dirty = True
		except: pass

		try:

			if results.total_filament:
				analysisResult['total_filament'] = results.total_filament

		except: pass

		if dirty:
			metadata = self.getFileMetadata(basename)
			metadata["gcodeAnalysis"] = analysisResult
			self._metadata[basename] = metadata
			self._metadataDirty = True
			self._saveMetadata()

		eventManager().fire(Events.METADATA_ANALYSIS_FINISHED, {"file": basename, "result": analysisResult})

	def _loadMetadata(self, migrate=False):
		if os.path.exists(self._metadataFile) and os.path.isfile(self._metadataFile):
			with self._metadataFileAccessMutex:
				with open(self._metadataFile, "r") as f:
					self._metadata = yaml.safe_load(f)

		if self._metadata is None:
			self._metadata = {}

		if migrate:
			self._migrateMetadata()

	def _migrateMetadata(self):
		self._logger.info("Migrating metadata if necessary...")

		updateCount = 0
		for metadata in self._metadata.values():
			if not "gcodeAnalysis" in metadata:
				continue

			updated = False

			if updated:
				updateCount += 1

		self._saveMetadata()

		self._logger.info("Updated %d sets of metadata to new format" % updateCount)

	def _saveMetadata(self, force=False):
		if not self._metadataDirty and not force:
			return

		with self._metadataFileAccessMutex:
			with open(self._metadataTempFile, "wb") as f:
				yaml.safe_dump(self._metadata, f, default_flow_style=False, indent="    ", allow_unicode=True)
				self._metadataDirty = False
			util.safeRename(self._metadataTempFile, self._metadataFile)

		self._loadMetadata()

	def _getBasicFilename(self, filename):
		if filename.startswith(self._uploadFolder):
			return filename[len(self._uploadFolder + os.path.sep):]
		else:
			return filename

	#~~ callback handling

	def registerCallback(self, callback):
		self._callbacks.append(callback)

	def unregisterCallback(self, callback):
		if callback in self._callbacks:
			self._callbacks.remove(callback)

	def _sendUpdateTrigger(self, type):
		for callback in self._callbacks:
			try: callback.sendEvent(type)
			except: pass

	#~~ file handling

	def addFile(self, file, destination, uploadCallback=None):
		"""
		Adds the given file for the given destination to the systems. Takes care of slicing if enabled and
		necessary.

		If the file's processing won't be finished directly with the return from this method but happen
		asynchronously in the background (e.g. due to slicing), returns a tuple containing the just added file's
		filename and False. Otherwise returns a tuple (filename, True).
		"""
		if not file or not destination:
			return None, True

		slicerEnabled = self._settings.getBoolean(["cura", "enabled"])
		filename = file.filename

		absolutePath = self.getAbsolutePath(filename, mustExist=False)
		valid = self.isValidFilename(filename)

		if absolutePath is None or (not slicerEnabled and not valid):
			return None, True

		file.save(absolutePath)

		if valid:
			return self.processPrintFile(absolutePath, destination, uploadCallback), True
		else:
			return filename, False

	def getFutureFileName(self, file):
		if not file:
			return None

		absolutePath = self.getAbsolutePath(file.filename, mustExist=False)
		if absolutePath is None:
			return None

		return self._getBasicFilename(absolutePath)

	def processPrintFile(self, absolutePath, destination, uploadCallback=None):
		if absolutePath is None:
			return None

		filename = self._getBasicFilename(absolutePath)

		if filename in self._metadata:
			# delete existing metadata entry, since the file is going to get overwritten
			del self._metadata[filename]
			self._metadataDirty = True
			self._saveMetadata()

		self._metadataAnalyzer.addFileToQueue(os.path.basename(absolutePath))

		if uploadCallback is not None:
			return uploadCallback(filename, absolutePath, destination)
		else:
			return filename

	def saveCloudPrintFile(self, absolutePath, fileInfo, destination, uploadCallback=None):
		if absolutePath is None:
			return None

		filename = self._getBasicFilename(absolutePath)

		self._metadataDirty = True
		self._metadata[filename] = {
			"cloud_id": fileInfo["id"],
			"gcodeAnalysis": fileInfo["info"],
			"printFileName": fileInfo["printFileName"],
			"printer": fileInfo["printer"],
			"material": fileInfo["material"],
			"quality": fileInfo["quality"],
			"image": fileInfo["image"],
			"created": fileInfo["created"],
			"prints": {
				"success": 0,
				"failure": 0,
				"last": {
					"date": None,
					"success": None
				}
			}
		}

		self._saveMetadata()

		if uploadCallback is not None:
			return uploadCallback(filename, absolutePath, destination)
		else:
			return filename

	def getFutureFilename(self, file):
		if not file:
			return None

		absolutePath = self.getAbsolutePath(file.filename, mustExist=False)
		if absolutePath is None:
			return None

		return self._getBasicFilename(absolutePath)

	def removeFile(self, filename):
		filename = self._getBasicFilename(filename)
		absolutePath = self.getAbsolutePath(filename)

		if absolutePath is None:
			return

		name, ext = absolutePath.rsplit(".", 1)
		stlPath = name + ".stl"

		os.remove(absolutePath)
		if os.path.exists(stlPath):
			os.remove(stlPath)

		self.removeFileFromMetadata(filename)

		eventManager().fire(Events.FILE_DELETED, {"filename": filename})

	def removeFileFromMetadata(self, filename):
		if filename in self._metadata:
			del self._metadata[filename]
			self._metadataDirty = True
			self._saveMetadata()

	def getAbsolutePath(self, filename, mustExist=True):
		"""
		Returns the absolute path of the given filename in the correct upload folder.

		Ensures that the file
		<ul>
		  <li>has any of the extensions listed in SUPPORTED_EXTENSIONS</li>
		  <li>exists and is a file (not a directory) if "mustExist" is set to True</li>
		</ul>

		@param filename the name of the file for which to determine the absolute path
		@param mustExist if set to true, the method also checks if the file exists and is a file
		@return the absolute path of the file or None if the file is not valid
		"""
		filename = self._getBasicFilename(filename)

		if not util.isAllowedFile(filename.lower(), set(self.SUPPORTED_EXTENSIONS)):
			return None

		# TODO: detect which type of file and add in the extra folder portion
		secure = os.path.join(self._uploadFolder, secure_filename(self._getBasicFilename(filename)))

		if mustExist and (not os.path.exists(secure) or not os.path.isfile(secure)):
			return None

		return secure

	def getAllFilenames(self):
		return [x["name"] for x in self.getAllFileData()]

	def getAllFileData(self):
		files = []
		for osFile in os.listdir(self._uploadFolder):
			fileData = self.getFileData(osFile)
			if fileData is not None:
				files.append(fileData)

		return files

	def getFileData(self, filename):
		if not filename:
			return

		filename = self._getBasicFilename(filename)

		# TODO: Make this more robust when STLs will be viewable from the client
		if self.isDesignFileName(filename):
			return

		absolutePath = self.getAbsolutePath(filename)
		if absolutePath is None:
			return None

		statResult = os.stat(absolutePath)
		fileData = {
			"name": filename,
			"printFileName": None,
			"size": statResult.st_size,
			"origin": FileDestinations.LOCAL,
			"date": int(statResult.st_ctime)
		}

		# enrich with additional metadata from analysis if available
		fmd = self._metadata.get(filename)
		if fmd:
			for key in fmd.keys():
				if key == "prints":
					val = fmd[key]
					last = None
					if "last" in val and val["last"] is not None:
						last = {
							"date": val["last"]["date"],
							"success": val["last"]["success"]
						}
						if "lastPrintTime" in val["last"] and val["last"]["lastPrintTime"] is not None:
							last["lastPrintTime"] = val["last"]["lastPrintTime"]
					prints = {
						"success": val["success"],
						"failure": val["failure"],
						"last": last
					}
					fileData["prints"] = prints
				else:
					fileData[key] = fmd[key]

		return fileData

	def getFileCloudId(self, filename):
		if filename:
			filename = self._getBasicFilename(filename)

			fmd = self._metadata.get(filename)
			if fmd:
				return fmd.get('cloud_id')

		return None

	def getFileByCloudId(self, cloudId):
		if cloudId:
			for f in self._metadata:
				fCloudId = self._metadata[f].get('cloud_id')
				if fCloudId == cloudId:
					return f

		return None

	def getFileMetadata(self, filename):
		filename = self._getBasicFilename(filename)
		fmd = self._metadata.get(filename)
		if fmd:
			return fmd
		else:
			return {
				"prints": {
					"success": 0,
					"failure": 0,
					"last": None
				}
			}

	def setFileMetadata(self, filename, metadata):
		filename = self._getBasicFilename(filename)
		self._metadata[filename] = metadata
		self._metadataDirty = True

	def getPrintFileName(self, filename):
		filename = self._getBasicFilename(filename)

		fmd = self.getFileMetadata(filename)

		if "printFileName" in fmd:
			return fmd["printFileName"]
		else:
			return { "printFileName": None }

	def setPrintFileName(self, filename, printFileName):
		filename = self._getBasicFilename(filename)
		absolutePath = self.getAbsolutePath(filename)
		if absolutePath is None:
			return

		metadata = self.getFileMetadata(filename)
		if metadata is None:
			return

		if "printFileName" in metadata:
			metadata["printFileName"] = printFileName
		else:
			metadata["printFileName"] = filename

		self.setFileMetadata(filename, metadata)

	#~~ print job data

	def printSucceeded(self, filename, printTime = None, layerCount = None):
		filename = self._getBasicFilename(filename)
		absolutePath = self.getAbsolutePath(filename)
		if absolutePath is None:
			return

		metadata = self.getFileMetadata(filename)
		metadata["prints"]["success"] += 1
		metadata["prints"]["last"] = {
			"date": time.time(),
			"success": True
		}

		if metadata.get('gcodeAnalysis') is None:
			metadata['gcodeAnalysis'] = {}

		if printTime is not None:
			metadata["prints"]["last"]["lastPrintTime"] = printTime
			metadata["gcodeAnalysis"]["print_time"] = printTime

		if layerCount is not None and ("layer_count" not in metadata["gcodeAnalysis"] or not metadata["gcodeAnalysis"]["layer_count"]):
			metadata["gcodeAnalysis"]["layer_count"] = layerCount

		self.setFileMetadata(filename, metadata)
		self._saveMetadata()

	def printFailed(self, filename, printTime):
		filename = self._getBasicFilename(filename)
		absolutePath = self.getAbsolutePath(filename)
		if absolutePath is None:
			return

		metadata = self.getFileMetadata(filename)
		metadata["prints"]["failure"] += 1
		metadata["prints"]["last"] = {
			"date": time.time(),
			"success": False
		}

		if printTime is not None:
			metadata["prints"]["last"]["lastPrintTime"] = printTime

		self.setFileMetadata(filename, metadata)
		self._saveMetadata()

	#~~ analysis control

	def pauseAnalysis(self):
		self._metadataAnalyzer.pause()

	def resumeAnalysis(self):
		self._metadataAnalyzer.resume()

	#~~ Child API ~~~

class MetadataAnalyzer(object):
	def __init__(self, getPathCallback, loadedCallback):
		self._getPathCallback = getPathCallback
		self._loadedCallback = loadedCallback

		self._active = threading.Event()
		self._active.set()

		self._currentFile = None
		self._currentProgress = None
		self._stop = False

		self._queue = Queue.PriorityQueue()

		self._worker = threading.Thread(target=self._work)
		self._worker.daemon = True
		self._worker.start()

	def addFileToQueue(self, filename):
		self._logger.debug("Adding file %s to analysis queue (high priority)" % filename)
		self._queue.put((0, filename))

	def addFileToBacklog(self, filename):
		self._logger.debug("Adding file %s to analysis backlog (low priority)" % filename)
		self._queue.put((100, filename))

	def working(self):
		return self.isActive() and not (self._queue.empty() and self._currentFile is None)

	def isActive(self):
		return self._active.is_set()

	def pause(self):
		self._logger.debug("Pausing Print File analyzer")
		self._active.clear()

	def resume(self):
		self._logger.debug("Resuming Print File analyzer")
		self._active.set()

	def stop(self):
		self._stop = True

		#We might be waiting on a _queue.get()
		#We add a fake item so that _queue.get returns and we can kill the thread
		self._queue.put((0, None))

		if not self._active.isSet():
			#It's waiting on a _active.wait()
			self._active.set()

	def _work(self):
		aborted = None
		while not self._stop:
			if aborted is not None:
				filename = aborted
				aborted = None
				self._logger.debug("Got an aborted analysis job for file %s, processing this instead of first item in queue" % filename)
			else:
				(priority, filename) = self._queue.get()
				if filename is None:
					self._queue.task_done()
					if self._stop:
						break
					else:
						continue

				self._logger.debug("Processing file %s from queue (priority %d)" % (filename, priority))

			self._active.wait()

			if self._stop:
				break

			try:
				self._analyzeFile(filename)
				self._queue.task_done()
			except AnalysisAborted:
				aborted = filename
				self._logger.debug("Running analysis of file %s aborted" % filename)

		self._getPathCallback = None
		self._loadedCallback = None

	def _onParsingProgress(self, progress):
		self._currentProgress = progress

	def _analyzeFile(self, filename):
		raise NotImplementedError()

class MetadataAnalyzerResults(object):
	layerList = None
	extrusionAmount = [0]
	extrusionVolume = [0]
	totalMoveTimeMinute = 0
	filename = None

class AnalysisAborted(Exception):
	pass
