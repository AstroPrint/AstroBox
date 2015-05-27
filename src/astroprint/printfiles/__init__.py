# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__author__ = "Gina Häußge <osd@foosel.net>"
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
			if fileData is not None and "gcodeAnalysis" in fileData.keys():
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
			# if "estimatedPrintTime" in metadata["gcodeAnalysis"]:
			# 	estimatedPrintTime = metadata["gcodeAnalysis"]["estimatedPrintTime"]
			# 	if isinstance(estimatedPrintTime, (str, unicode)):
			# 		match = re.match(printTimeRe, estimatedPrintTime)
			# 		if match:
			# 			metadata["gcodeAnalysis"]["estimatedPrintTime"] = int(match.group(1)) * hoursToSeconds + int(match.group(2)) * minutesToSeconds + int(match.group(3))
			# 			self._metadataDirty = True
			# 			updated = True
			# if "filament" in metadata["gcodeAnalysis"]:
			# 	filament = metadata["gcodeAnalysis"]["filament"]
			# 	if isinstance(filament, (str, unicode)):
			# 		match = re.match(filamentRe, filament)
			# 		if match:
			# 			metadata["gcodeAnalysis"]["filament"] = {
			# 				"tool0": {
			# 					"length": int(float(match.group(1)) * 1000)
			# 				}
			# 			}
			# 			if match.group(3) is not None:
			# 				metadata["gcodeAnalysis"]["filament"]["tool0"].update({
			# 					"volume": float(match.group(3))
			# 				})
			# 			self._metadataDirty = True
			# 			updated = True
			# 	elif isinstance(filament, dict) and ("length" in filament.keys() or "volume" in filament.keys()):
			# 		metadata["gcodeAnalysis"]["filament"] = {
			# 			"tool0": {}
			# 		}
			# 		if "length" in filament.keys():
			# 			metadata["gcodeAnalysis"]["filament"]["tool0"].update({
			# 				"length": filament["length"]
			# 			})
			# 		if "volume" in filament.keys():
			# 			metadata["gcodeAnalysis"]["filament"]["tool0"].update({
			# 				"volume": filament["volume"]
			# 			})
			# 		self._metadataDirty = True
			# 		updated = True

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
			if curaEnabled and self.isDesignFileName(filename):
				return self.processDesign(absolutePath, destination, uploadCallback), False
			else:
				return filename, False

			if slicerEnabled and self.isDesignFileName(filename):
				self.processDesign(absolutePath, destination, uploadCallback)
			return filename, False

	def getFutureFileName(self, file):
		if not file:
			return None

		absolutePath = self.getAbsolutePath(file.filename, mustExist=False)
		if absolutePath is None:
			return None

		return self._getBasicFilename(absolutePath)

	def processDesign(self, absolutePath, destination, uploadCallback=None):
		
		def designProcessed(stlPath, filePath, error=None):
			if error:
				eventManager().fire(Events.SLICING_FAILED, {"stl": self._getBasicFilename(stlPath), "gcode": self._getBasicFilename(filePath), "reason": error})
				if os.path.exists(stlPath):
					os.remove(stlPath)
			else:
				slicingStop = time.time()
				eventManager().fire(Events.SLICING_DONE, {"stl": self._getBasicFilename(stlPath), "gcode": self._getBasicFilename(filePath), "time": slicingStop - slicingStart})
				self.processPrintFile(filePath, destination, uploadCallback)

		eventManager().fire(Events.SLICING_STARTED, {"stl": self._getBasicFilename(absolutePath), "gcode": self._getBasicFilename(filePath)})
		cura.process_file(config, filePath, absolutePath, designProcessed, [absolutePath, filePath])

		return self._getBasicFilename(filePath)

	def processPrintFile(self, absolutePath, destination, uploadCallback=None):
		if absolutePath is None:
			return None

		filename = self._getBasicFilename(absolutePath)

		if filename in self._metadata.keys():
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

	def removeFileFromMetadata(self, filename):
		if filename in self._metadata.keys():
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
		print self.getAllFileData()
		return map(lambda x: x["name"], self.getAllFileData())

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
			"size": statResult.st_size,
			"origin": FileDestinations.LOCAL,
			"date": int(statResult.st_ctime)
		}

		# enrich with additional metadata from analysis if available
		if filename in self._metadata.keys():
			for key in self._metadata[filename].keys():
				if key == "prints":
					val = self._metadata[filename][key]
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
					fileData[key] = self._metadata[filename][key]

		return fileData

	def getFileCloudId(self, filename):
		if filename:
			filename = self._getBasicFilename(filename)
		
			if filename in self._metadata.keys() and 'cloud_id' in self._metadata[filename].keys():
				return self._metadata[filename]['cloud_id']

		return None

	def getFileByCloudId(self, cloudId):
		if cloudId:
			for f in self._metadata.keys():
				if 'cloud_id' in self._metadata[f] and self._metadata[f]['cloud_id'] == cloudId:
					return f

		return None

	def getFileMetadata(self, filename):
		filename = self._getBasicFilename(filename)
		if filename in self._metadata.keys():
			return self._metadata[filename]
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

		if "gcodeAnalysis" not in metadata:
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

	def changeLastPrintSuccess(self, filename, succeeded):
		filename = self._getBasicFilename(filename)
		absolutePath = self.getAbsolutePath(filename)
		if absolutePath is None:
			return

		metadata = self.getFileMetadata(filename)
		if metadata is None:
			return

		if "prints" in metadata.keys():
			if "last" in metadata.keys() and metadata["prints"]["last"] is not None:
				currentSucceeded = metadata["prints"]["last"]["success"]
				if currentSucceeded != succeeded:
					metadata["prints"]["last"]["success"] = succeeded
					if currentSucceeded:
						# last print job was counted as success but actually failed
						metadata["prints"]["success"] -= 1
						metadata["prints"]["failure"] += 1
					else:
						# last print job was counted as a failure but actually succeeded
						metadata["prints"]["success"] += 1
						metadata["prints"]["failure"] -= 1
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
		if not self._active.isSet():
			#It's waiting on a _active.wait()
			self._active.set()
		else:
			#It's waiting on a _queue.get()
			#We add a fake item so that _queue.get returns and we can kill the thread
			self._queue.put((0, None))

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
