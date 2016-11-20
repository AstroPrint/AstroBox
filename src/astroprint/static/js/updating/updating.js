/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

$.ajaxSetup({
  cache: false,
  headers: {
    "X-Api-Key": UI_API_KEY
  }
});

var SoftwareUpdateProgress = Backbone.View.extend({
  el: '#updating-view',
  _socket: null,
  _autoReconnecting: false,
  _autoReconnectTrial: 0,
  _autoReconnectTimeouts: [1, 1, 2, 3, 5, 8, 13, 20, 40, 100],
  events: {
    'click .error button.close': 'closeClicked',
    'click .error button.retry': 'installClicked',
    'click .info button': 'installClicked'
  },
  initialize: function()
  {
    this.connect(WS_TOKEN);
    this.updateInfo(updateInfo.progress, updateInfo.message);
  },
  connect: function(token)
  {
    this._socket = new SockJS(SOCKJS_URI+'?token='+token);
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
  _onConnect: function()
  {
    self._autoReconnecting = false;
    self._autoReconnectTrial = 0;
  },
  _onClose: function(e)
  {
    if (e && e.code == 1000) {
      // it was us calling close
      return;
    }

    if (this._autoReconnectTrial < this._autoReconnectTimeouts.length) {
      var timeout = this._autoReconnectTimeouts[this._autoReconnectTrial];
      console.log("Reconnect trial #" + this._autoReconnectTrial + ", waiting " + timeout + "s");
      setTimeout(_.bind(this.reconnect, this), timeout * 1000);
      this._autoReconnectTrial++;
    } else {
      this._onReconnectFailed();
    }
  },
  _onReconnectFailed: function()
  {
    console.error('reconnect failed');
    //We're going to try to reload a see what happens
    location.reload();
  },
  _onMessage: function(e)
  {
    for (var prop in e.data) {
      var data = e.data[prop];

      switch (prop) {
        case "connected":
          // update the current UI API key and send it with any request
          UI_API_KEY = data["apikey"];
          $.ajaxSetup({
            headers: {"X-Api-Key": UI_API_KEY}
          });
        break;

        case "event":
          var type = data["type"];
          var payload = data["payload"];

          if (type == 'SoftwareUpdateEvent') {
            var payload = data["payload"];

            if (payload.completed) {
              if (payload.success) {
                setTimeout(function() {
                  location.reload();
                }, 9000);
              } else {
                //error case here
                this.$el.find('.progress-info').addClass('hide');
                this.$el.find('.error').removeClass('hide');
                this.$el.find('.info').addClass('hide');
              }
            } else if (payload.message) {
              this.updateInfo(payload.progress, payload.message);
            }
          }
        break;
      }
    }
  },
  updateInfo: function(progress, message)
  {
    if (progress) {
      this.$('.progress-info .progress .meter').css('width', (progress * 100) + '%');
    }

    if (message) {
      this.$('h3.message').text(message);
    }
  },
  closeClicked: function(e)
  {
    e.preventDefault();
    location.href="/#settings/software-update";
    location.reload();
  },
  installClicked: function(e)
  {
    e.preventDefault();
    var loadingBtn = $(e).closest('.loading-button');
    loadingBtn.addClass('loading');
    $.ajax({
      url: API_BASEURL + 'settings/software/update',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/json',
      data: JSON.stringify({
        release_id: RELEASE_ID
      }),
      success: _.bind(function() {
        this.$el.find('.progress-info').removeClass('hide');
        this.$el.find('.error').addClass('hide');
        this.$el.find('.info').addClass('hide');
      }, this),
      error: _.bind(function(xhr) {
        this.$el.find('.progress-info').addClass('hide');
        this.$el.find('.error').removeClass('hide');
        this.$el.find('.info').addClass('hide');
      }, this),
      complete: function() {
        loadingBtn.removeClass('loading');
      }
    });
  }
});

var view = new SoftwareUpdateProgress();
