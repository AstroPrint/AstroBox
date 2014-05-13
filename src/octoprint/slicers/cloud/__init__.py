__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"

import importlib

# This dictionay represent the available cloud slicers
# <Slicer Name> : [<Slicer class name>, <Slicer module name>]
cloud_slicer_map = {
	"ProvenToPrint" : ["ProvenToPrintSlicer", "proven_to_print"] 
}

class CloudSlicer(object):

	@staticmethod
	def get_slicer_instance(name):
		module = importlib.import_module("octoprint.slicers.cloud."+cloud_slicer_map[name][1])
		class_ = getattr(module, cloud_slicer_map[name][0])
		return class_();

	def process_file(self, config, gcodePath, stlPath, procesingCb=None, completionCb=None):
		import threading

		def start_thread():
			self.start_slice_job(config, gcodePath, stlPath, procesingCb, completionCb)

		thread = threading.Thread(target=start_thread)
		thread.start()

	#CloudSlicer API. Implement these functions
	@staticmethod
	def cloud_slicer_enabled():
		return False

	def get_private_key(email, password):
		return False

	def get_public_key(self, email, private_key):
		return None

	def get_upload_info(self, filePath):
		return '', {}, '' #url, form params, redirect url

	def start_slice_job(self, config, gcodePath, stlPath, procesingCb, completionCb):
		completionCb(stlPath, gcodePath, "Processing function not implemented")

	def refresh_files(self):
		return None

	def download_gcode_file(self, fileId, destFile, progressCb, successCb, errorCb):
		errorCb('Download function is not implemented')