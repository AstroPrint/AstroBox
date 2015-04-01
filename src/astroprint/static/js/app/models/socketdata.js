/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var SocketData = Backbone.Model.extend({
	connectionView: null,
	_socket: null,
	_autoReconnectTrial: 0,
    _nextReconnectAttempt: null,
	_autoReconnectTimeouts: [1, 1, 2, 3, 5, 8, 13, 20, 40, 100],
	currentState: 0,
    lockedUser: null, //username or null
	defaults: {
        printing: false,
        paused: false,
        camera: false,
        printing_progress: {
            percent: 0.0,
            time_left: 0
        },
		temps: {
			bed: {
				actual: 0,
				target: 0
			},
			extruder: {
				actual: 0,
				target: 0
			}
		},
        astroprint: {
            status: null
        },
        printer: {
            status: null
        },
        print_capture: null
	},
    initialize: function()
    {
        this.set('printing', initial_states.printing);
        this.set('paused', initial_states.paused);
        this.set('print_capture', initial_states.print_capture);
    },
	connect: function()
	{
		this.connectionView.setServerConnection('blink-animation');

        var options = {};
        if (SOCKJS_DEBUG) {
            options["debug"] = true;
        }

        this._socket = new SockJS(SOCKJS_URI, undefined, options);
        this._socket.onopen = _.bind(this._onConnect, this);
        this._socket.onclose = _.bind(this._onClose, this);
        this._socket.onmessage = _.bind(this._onMessage, this);
	},
   	reconnect: function() {
        delete this._socket;
        this.connect();
    },
   	_onConnect: function() {
        if (this._nextReconnectAttempt) {
            clearTimeout(this._nextReconnectAttempt);
            this._nextReconnectAttempt = null;
        }
        this._autoReconnectTrial = 0;
        this.connectionView.setServerConnection('connected');

        //Get some initials
    },
    _onClose: function() {
    	this.connectionView.setServerConnection('failed');
    	this.connectionView.setPrinterConnection('failed');
        this.connectionView.setAstroprintConnection('failed');
    	this._currentState = 0;

        if (this._autoReconnectTrial < this._autoReconnectTimeouts.length) {
            var timeout = this._autoReconnectTimeouts[this._autoReconnectTrial];

            console.log("Reconnect trial #" + this._autoReconnectTrial + ", waiting " + timeout + "s");

            this._nextReconnectAttempt = setTimeout(_.bind(this.reconnect, this), timeout * 1000);
            this._autoReconnectTrial++;
        } else {
            this._onReconnectFailed();
        }
    },
    _onReconnectFailed: function() {
		console.error('reconnect failed');
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

                    break;
                }

                case "current": {
                    var flags = data.state.flags;

                	if (data.temps.length) {
	                	var temps = data.temps[data.temps.length-1];
	                	this.set('temps', {
	                		bed: temps.bed,
	                		extruder: temps.tool0
	                	});
	                }

	                if (data.state && data.state.text != this.currentState) {
	                	this.currentState = data.state.text;
                        var connectionClass = 'blink-animation';
                        var printerStatus = 'connecting';
                        
	                	if (flags.error) {
                            connectionClass = 'failed';
                            printerStatus = 'failed';
	                	} else if (flags.operational) {
                            connectionClass = 'connected';
                            printerStatus = 'connected';
	                	}
                        
                        this.connectionView.setPrinterConnection(connectionClass);
                        this.set('printer', {status: printerStatus });
	                }

                    if (!flags.paused) {
                        this.set('printing', flags.printing);
                    }
                    this.set('paused', flags.paused);
                    this.set('camera', flags.camera);

                    if (flags.printing) {
                        var progress = data.progress;

                        this.set('printing_progress', {
                            filename: data.job.file.name,
                            rendered_image: data.job.file.rendered_image,
                            layer_count: data.job.layerCount,
                            current_layer: progress.currentLayer,
                            percent: progress.completion ? progress.completion.toFixed(1) : 0,
                            time_left: data.progress.printTimeLeft,
                            time_elapsed: progress.printTime ? progress.printTime : 0,
                            heating_up: flags.heatingUp
                        });
                    }

                    break;
                }

                case "event": {
                    var type = data["type"];
                    var payload = data["payload"];

                    switch(type) {
                        case 'MetadataAnalysisFinished':
                            app.eventManager.trigger('astrobox:MetadataAnalysisFinished', payload);
                            break;

                        case 'CloudDownloadEvent':
                            app.eventManager.trigger('astrobox:cloudDownloadEvent', payload);
                            break;

                        case 'AstroPrintStatus':
                            switch(payload) {
                                case 'connecting':
                                    this.connectionView.setAstroprintConnection('blink-animation');
                                    break;

                                case 'connected':
                                    this.connectionView.setAstroprintConnection('connected');
                                    break;

                                case 'disconnected':
                                case 'error':
                                    this.connectionView.setAstroprintConnection('failed');
                                    break;

                                default:
                                console.log('astroprintStatus unkonwn event: '+payload);
                            }
                            this.set('astroprint', { status: payload });
                            break;

                        case 'LockStatusChanged':
                            location.reload();
                            break;

                        case 'PrintCaptureInfoChanged':
                            this.set('print_capture', payload);
                            break;

                        default:
                            console.warn('Unkonwn event received: '+type);
                    }

                    break;
                }
            }
        }
    }
});