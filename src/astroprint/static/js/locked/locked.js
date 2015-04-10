$.ajaxSetup({
    type: 'POST',
    cache: false,
    headers: { 
    	"X-Api-Key": UI_API_KEY
    }
});

LoginForm = Backbone.View.extend({
	el: '#login-form',
	events: {
		'submit': 'onSubmit'
	},
	_socket: null,
	_autoReconnecting: false,
	_autoReconnectTrial: 0,
	_autoReconnectTimeouts: [1, 1, 2, 3, 5, 8, 13, 20, 40, 100],
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

            if (type == "LockStatusChanged") {
            	var payload = data["payload"];

            	if (!payload) {
            		location.reload();
            	}
            }
        }
    },
	onSubmit: function(e)
	{
		e.preventDefault();

		var loadingBtn = this.$('.loading-button');

		loadingBtn.addClass('loading');

		$.ajax({
			url: '/api/login',
			data: this.$el.serializeArray()
		})
		.done(function(){
			location.reload();
		})
		.fail(function(){
			noty({text: "Invalid Password", timeout: 3000});
			loadingBtn.removeClass('loading');
		});

		return false;
	}
});

var form = new LoginForm();