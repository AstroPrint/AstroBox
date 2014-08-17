/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var SocketData = Backbone.Model.extend({
	connectionView: null,
	_socket: null,
	_autoReconnecting: false,
	_autoReconnectTrial: 0,
	_autoReconnectTimeouts: [1, 1, 2, 3, 5, 8, 13, 20, 40, 100],
	currentState: 0,
	defaults: {
        printing: false,
        paused: false,
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
        }
	},
    initialize: function()
    {
        this.set('printing', initial_states.printing);
        this.set('paused', initial_states.paused);
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

                    break;
                }

                case "current": {
                    //console.log(data);

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
                        
	                	if (flags.error) {
                            connectionClass = 'failed';
	                	} else if (flags.operational) {
                            connectionClass = 'connected';
	                	}
                        
                        this.connectionView.setPrinterConnection(connectionClass);
	                }

                    if (this.get('printing') != flags.printing) {
                        if (!flags.paused) {
                            this.set('printing', flags.printing);
                        }
                    }

                    if (this.get('paused') != flags.paused) {
                        this.set('paused', flags.paused);
                    }

                    if (flags.printing) {
                        var progress = data.progress;

                        //calculate new estimate time
                        var base1Progress = progress.completion / 100.0;
                        var originalEstimatedTime = data.job.estimatedPrintTime;
                        var estimatedTimeLeft = originalEstimatedTime *  (1.0 - base1Progress );
                        var elaspedTimeVariance = progress.printTime - (originalEstimatedTime - estimatedTimeLeft);
                        var adjustedEstimatedTime = originalEstimatedTime + elaspedTimeVariance;
                        var newEstimatedTimeLeft = adjustedEstimatedTime * (1.0 -  base1Progress);

                        this.set('printing_progress', {
                            filename: data.job.file.name,
                            layer_count: data.job.layerCount,
                            current_layer: progress.currentLayer,
                            percent: progress.completion ? progress.completion.toFixed(1) : 0,
                            time_left: progress.completion >= 100.0 ? 0.0 : newEstimatedTimeLeft,
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

                        default:
                            console.warn('Unkonwn event received: '+type);
                    }

                    break;
                }
            }
        }
    }
});