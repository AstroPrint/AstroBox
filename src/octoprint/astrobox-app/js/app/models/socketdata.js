/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var SocketData = Backbone.Model.extend({
	connectionView: null,
    homeView: null,
	_socket: null,
	_autoReconnecting: false,
	_autoReconnectTrial: 0,
	_autoReconnectTimeouts: [1, 1, 2, 3, 5, 8, 13, 20, 40, 100],
	currentState: 0,
	defaults: {
		temps: {
			bed: {
				actual: 0,
				set: 0
			},
			extruder: {
				actual: 0,
				set: 0
			}
		}
	},
	connect: function()
	{
		this.connectionView.setServerConnection('blink-animation');

        var options = {};
        if (SOCKJS_DEBUG) {
            options["debug"] = true;
        }

        var self = this;
        this._socket = new SockJS(SOCKJS_URI, undefined, options);
        this._socket.onopen = function(){ self._onConnect() };
        this._socket.onclose = function(){ self._onClose() };
        this._socket.onmessage = function(e){ self._onMessage(e) };
	},
   	reconnect: function() {
        delete this._socket;
        this.connect();
    },
   	_onConnect: function() {
        self._autoReconnecting = false;
        self._autoReconnectTrial = 0;
        this.connectionView.setServerConnection('connected');
    },
    _onClose: function() {
    	this.connectionView.setServerConnection('failed');
    	this.connectionView.setPrinterConnection('failed');
    	this._currentState = 0;

        /*$("#offline_overlay_message").html(
            "The server appears to be offline, at least I'm not getting any response from it. I'll try to reconnect " +
                "automatically <strong>over the next couple of minutes</strong>, however you are welcome to try a manual reconnect " +
                "anytime using the button below."
        );
        if (!$("#offline_overlay").is(":visible"))
            $("#offline_overlay").show();*/

        if (this._autoReconnectTrial < this._autoReconnectTimeouts.length) {
            var timeout = this._autoReconnectTimeouts[this._autoReconnectTrial];
            console.log("Reconnect trial #" + this._autoReconnectTrial + ", waiting " + timeout + "s");
            var self = this;
            setTimeout(function(){self.reconnect()}, timeout * 1000);
            this._autoReconnectTrial++;
        } else {
            this._onReconnectFailed();
        }
    },
    _onReconnectFailed: function() {
        /*$("#offline_overlay_message").html(
            "The server appears to be offline, at least I'm not getting any response from it. I <strong>could not reconnect automatically</strong>, " +
                "but you may try a manual reconnect using the button below."
        );*/
		console.error('recoonect failed');
    },
    _onMessage: function(e) {
        for (var prop in e.data) {
            var data = e.data[prop];

            switch (prop) {
                case "connected": {
                    // update the current UI API key and send it with any request
                    UI_API_KEY = data["apikey"];
                    $.ajaxSetup({
                        headers: {"X-Api-Key": UI_API_KEY}
                    });

                    this.connectionView.connect();

                    /*if ($("#offline_overlay").is(":visible")) {
                        $("#offline_overlay").hide();
                        self.logViewModel.requestData();
                        self.timelapseViewModel.requestData();
                        $("#webcam_image").attr("src", CONFIG_WEBCAM_STREAM + "?" + new Date().getTime());
                        self.loginStateViewModel.requestData();
                        self.gcodeFilesViewModel.requestData();
                        self.gcodeViewModel.reset();

                        if ($('#tabs li[class="active"] a').attr("href") == "#control") {
                            $("#webcam_image").attr("src", CONFIG_WEBCAM_STREAM + "?" + new Date().getTime());
                        }
                    }*/

                    break;
                }
                /*case "history": {
                    self.connectionViewModel.fromHistoryData(data);
                    self.printerStateViewModel.fromHistoryData(data);
                    self.temperatureViewModel.fromHistoryData(data);
                    self.controlViewModel.fromHistoryData(data);
                    self.terminalViewModel.fromHistoryData(data);
                    self.timelapseViewModel.fromHistoryData(data);
                    self.gcodeViewModel.fromHistoryData(data);
                    self.gcodeFilesViewModel.fromCurrentData(data);
                    break;
                }*/
                case "current": {
                	if (data.temps.length) {
	                	var temps = data.temps[data.temps.length-1];
	                	this.set('temps', {
	                		bed: temps.bed,
	                		extruder: temps.tool0
	                	});
	                }

	                if (data.state && data.state.state != this.currentState) {
	                	this.currentState = data.state.state;
	                	if (data.state.flags.error) {
        					this.connectionView.setPrinterConnection('failed');
	                	} else if (data.state.flags.operational) {
	                		this.connectionView.setPrinterConnection('connected');
	                	}
	                }

                    //self.connectionViewModel.fromCurrentData(data);
                    //self.printerStateViewModel.fromCurrentData(data);
                    //self.temperatureViewModel.fromCurrentData(data);
                    //self.controlViewModel.fromCurrentData(data);
                    //self.terminalViewModel.fromCurrentData(data);
                    //self.timelapseViewModel.fromCurrentData(data);
                    //self.gcodeViewModel.fromCurrentData(data);
                    //self.gcodeFilesViewModel.fromCurrentData(data);
                    break;
                }
                case "event": {
                    var type = data["type"];
                    var payload = data["payload"];

                    if (type == "cloudDownloadEvent") {
                        this.homeView.designsView.downloadProgress(payload);
                    }

                    /*var gcodeUploadProgress = $("#gcode_upload_progress");
                    var gcodeUploadProgressBar = $(".bar", gcodeUploadProgress);

                    if ((type == "UpdatedFiles" && payload.type == "gcode") || type == "MetadataAnalysisFinished") {
                        gcodeFilesViewModel.requestData();
                    } else if (type == "MovieRendering") {
                        $.pnotify({title: "Rendering timelapse", text: "Now rendering timelapse " + payload.movie_basename});
                    } else if (type == "MovieDone") {
                        $.pnotify({title: "Timelapse ready", text: "New timelapse " + payload.movie_basename + " is done rendering."});
                        timelapseViewModel.requestData();
                    } else if (type == "MovieFailed") {
                        $.pnotify({title: "Rendering failed", text: "Rendering of timelapse " + payload.movie_basename + " failed, return code " + payload.returncode, type: "error"});
                    } else if (type == "SlicingStarted") {
                        gcodeUploadProgress.addClass("progress-striped").addClass("active");
                        gcodeUploadProgressBar.css("width", "100%");
                        gcodeUploadProgressBar.text("Slicing ...");
                    } else if (type == "SlicingDone") {
                        gcodeUploadProgress.removeClass("progress-striped").removeClass("active");
                        gcodeUploadProgressBar.css("width", "0%");
                        gcodeUploadProgressBar.text("");
                        $.pnotify({title: "Slicing done", text: "Sliced " + payload.stl + " to " + payload.gcode + ", took " + _.sprintf("%.2f", payload.time) + " seconds"});
                        gcodeFilesViewModel.requestData(payload.gcode);
                    } else if (type == "SlicingFailed") {
                        gcodeUploadProgress.removeClass("progress-striped").removeClass("active");
                        gcodeUploadProgressBar.css("width", "0%");
                        gcodeUploadProgressBar.text("");
                        $.pnotify({title: "Slicing failed", text: "Could not slice " + payload.stl + " to " + payload.gcode + ": " + payload.reason, type: "error"});
                    } else if (type == "TransferStarted") {
                        gcodeUploadProgress.addClass("progress-striped").addClass("active");
                        gcodeUploadProgressBar.css("width", "100%");
                        gcodeUploadProgressBar.text("Streaming ...");
                    } else if (type == "TransferDone") {
                        gcodeUploadProgress.removeClass("progress-striped").removeClass("active");
                        gcodeUploadProgressBar.css("width", "0%");
                        gcodeUploadProgressBar.text("");
                        $.pnotify({title: "Streaming done", text: "Streamed " + payload.local + " to " + payload.remote + " on SD, took " + _.sprintf("%.2f", payload.time) + " seconds"});
                        gcodeFilesViewModel.requestData(payload.remote, "sdcard");
                    }*/
                    break;
                }
                /*case "feedbackCommandOutput": {
                    self.controlViewModel.fromFeedbackCommandData(data);
                    break;
                }
                case "timelapse": {
                    self.printerStateViewModel.fromTimelapseData(data);
                    break;
                }*/
            }
        }
    }
});