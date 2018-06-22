/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

window.AP_SESSION_ID = null;

var SocketData = Backbone.Model.extend({
  connectionView: null,
  _socket: null,
  _autoReconnectTrial: 0,
  _nextReconnectAttempt: null,
  _autoReconnectTimeouts: [1, 1, 2, 3, 5, 8, 13, 20, 40, 100],
  currentState: 0,
  loggedUser: LOGGED_USER, //username or null
  defaults: {
    box_reachable: 'unreachable', //unreachable, reachable, checking
    online: false,
    printing: false,
    paused: false,
    camera: false,
    printing_progress: {
      percent: 0.0,
      time_left: 0
    },
    temps: {},
    astroprint: {
      status: null
    },
    printer: {
      status: null
    },
    print_capture: null,
    tool: null,
    printing_speed: "100",
    printing_flow: "100"
  },
  extruder_count: null,
  initialize: function()
  {
    this.set('printing', initial_states.printing || initial_states.paused);
    this.set('paused', initial_states.paused);
    this.set('online', initial_states.online);
    this.set('print_capture', initial_states.print_capture);

    //See if we need to check for sofware version
    if (initial_states.checkSoftware && initial_states.online) {
      $.get(API_BASEURL + 'settings/software/check')
        .done(_.bind(function(data) {
          if (data.update_available) {
            this.trigger('new_sw_release');
          }
        }, this));
    }
  },
  connect: function(token)
  {
    this.set('box_reachable', 'checking');

    var options = {};
    if (SOCKJS_DEBUG) {
      options["debug"] = true;
    }

    this._socket = new SockJS(SOCKJS_URI+'?token='+token, undefined, options);
    this._socket.onopen = _.bind(this._onConnect, this);
    this._socket.onclose = _.bind(this._onClose, this);
    this._socket.onmessage = _.bind(this._onMessage, this);
  },
  reconnect: function() {
    if (this._socket) {
      this._socket.close();
      delete this._socket;
    }

    $.getJSON('/wsToken')
      .done(_.bind(function(data){
        if (data && data.ws_token) {
          this.connect(data.ws_token);
        }
      }, this))
      .fail(_.bind(function(){
        this._onClose();
      }, this));
  },
  _onConnect: function() {
    if (this._nextReconnectAttempt) {
      clearTimeout(this._nextReconnectAttempt);
      this._nextReconnectAttempt = null;
    }
    this._autoReconnectTrial = 0;
    this.set('box_reachable', 'reachable');
    //Get some initials
    if (this.extruder_count == null) {
      this.extruder_count = (app.printerProfile.toJSON())['extruder_count'];
    }
  },
  _onClose: function(e) {
    if (e && e.code == 1000) {
      // it was us calling close
      return;
    }

    this.set('box_reachable', 'unreachable');
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
          AP_SESSION_ID = data["sessionId"];
          $.ajaxSetup({
            headers: {"X-Api-Key": UI_API_KEY}
          });

          this.connectionView.connect();
        }
        break;

        case "current": {
          var flags = data.state.flags;
          if (data.temps.length) {
            var temps = data.temps[data.temps.length-1];
            var extruders = [];
            var tool = null;

            for (var i = 0; i < this.extruder_count; i++) {
              if (temps['tool' + i]) {
                tool = { "current": temps['tool' + i].actual, "target": temps['tool' + i].target }
                extruders[i] = tool ;
              }
            }

            this.set('temps', {
              bed: temps.bed,
              extruders: extruders
            });
          }

          if (data.state && data.state.text != this.currentState) {
            this.currentState = data.state.text;
            connectionClass = '';
            printerStatus = '';

            if (data.state.state == 4) { //4 -> STATE_CONNECTING
              connectionClass = 'blink-animation';
              printerStatus = 'connecting';
            } else if (flags.closedOrError) {
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

          if (flags.printing || flags.paused) {
            var progress = data.progress;
            var job = data.job;

            var printFileName = job.file.printFileName ? job.file.printFileName : job.file.name

            this.set('printing_progress', {
              filename: job.file.name,
              printFileName: printFileName,
              rendered_image: job.file.rendered_image,
              layer_count: job.layerCount,
              current_layer: progress.currentLayer,
              percent: progress.completion ? progress.completion.toFixed(1) : 0,
              time_left: data.progress.printTimeLeft,
              time_elapsed: progress.printTime ? progress.printTime : 0,
              heating_up: flags.heatingUp
            });
          }

          this.set('tool', data.tool);
          this.set('printing_speed', data.printing_speed);
          this.set('printing_flow', data.printing_flow);
        }
        break;

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

            case 'CopyToHomeProgress':
              if(payload.observerId == AP_SESSION_ID){
                app.eventManager.trigger('astrobox:copyToHomeProgress', payload);
              }
            break;

            case 'ExternalDriveMounted':
              payload.action = 'mounted';
              app.eventManager.trigger('astrobox:externalDriveMounted', payload);
            break;

            case 'ExternalDriveEjected':
              payload.action = 'ejected';
              app.eventManager.trigger('astrobox:externalDriveEjected', payload);
            break;

            case 'ExternalDrivePhisicallyRemoved':
              payload.action = 'removed';
              app.eventManager.trigger('astrobox:externalDrivePhisicallyRemoved', payload);
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
              if (payload != this.loggedUser) {
                location.reload();
              }
            break;

            case 'PrintCaptureInfoChanged':
              this.set('print_capture', payload);
            break;

            case 'NetworkStatus':
              this.set('online', payload == 'online');
            break;

            case 'InternetConnectingStatus':
              app.eventManager.trigger('astrobox:InternetConnectingStatus', payload);
            break;

            case 'GstreamerEvent':
              app.eventManager.trigger('astrobox:videoStreamingEvent',payload);
            break;

            case 'SoftwareUpdateEvent':
              //We need to release so that the update screen shows up
              window.location.reload()
            break;

            case 'ToolChange':
              this.set('tool', data.tool);
              break;

            default:
              console.warn('Unkonwn event received: '+type);
          }
        }
        break;

        case 'commsData':
          app.eventManager.trigger('astrobox:commsData', {direction: data.direction, data: data.data.trim()});
        break;
      }
    }
  }
});
