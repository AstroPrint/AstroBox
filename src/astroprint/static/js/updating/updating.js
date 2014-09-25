/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
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
		this.connect();
	},
	connect: function()
	{
        this._socket = new SockJS(SOCKJS_URI);
        this._socket.onopen = _.bind(this._onConnect, this);
        this._socket.onclose = _.bind(this._onClose, this);
        this._socket.onmessage = _.bind(this._onMessage, this);
	},
   	reconnect: function() {
        delete this._socket;
        this.connect();
    },
   	_onConnect: function() {
        self._autoReconnecting = false;
        self._autoReconnectTrial = 0;
    },
    _onClose: function() {
        if (this._autoReconnectTrial < this._autoReconnectTimeouts.length) {
            var timeout = this._autoReconnectTimeouts[this._autoReconnectTrial];
            console.log("Reconnect trial #" + this._autoReconnectTrial + ", waiting " + timeout + "s");
            setTimeout(_.bind(this.reconnect, this), timeout * 1000);
            this._autoReconnectTrial++;
        } else {
            this._onReconnectFailed();
        }
    },
    _onReconnectFailed: function() {
		console.error('reconnect failed');
		//We're going to try to reload a see what happens
		location.reload();
    },
    _onMessage: function(e) {
    	if (e.data && e.data['event']) {
            var data = e.data['event'];
            var type = data["type"];

            switch(type) {
                case 'SoftwareUpdateEvent':
                    var payload = data["payload"];

                	if (payload.completed) {
                		if (payload.success) {
                            this.$el.find('h3.message').text('Restarting. Please wait..');
							$.ajax({
								type: 'POST',
								url: API_BASEURL + 'settings/software/restart'
							});
                            setTimeout(function() {
                                location.href = '/';
                            }, 6000);
						} else {
							//error case here
							this.$el.find('.progress').addClass('hide');
							this.$el.find('.error').removeClass('hide');
                            this.$el.find('.info').addClass('hide');
						}
                	} else if (payload.message) {
                		this.$el.find('h3.message').text(payload.message);
                	}
           	}
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
                this.$el.find('.progress').removeClass('hide');
                this.$el.find('.error').addClass('hide');
                this.$el.find('.info').addClass('hide');
            }, this),
            error: _.bind(function(xhr) {
                this.$el.find('.progress').addClass('hide');
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