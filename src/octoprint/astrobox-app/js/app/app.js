var AstroBoxApp = Backbone.View.extend({
	el: 'body',
	controlView: new ControlView(),
	connectionView: new ConnectionView(),
	turnoffView: new TurnoffView(),
	socketData: new SocketData(),
	initialize: function() {
		this.socketData.connectionView = this.connectionView;
		this.connectionView.socketData = this.socketData;
		this.socketData.connect();
		this.listenTo(this.socketData, 'change:temps', this.reportTempChange );
	},
	reportTempChange: function(s, value) {
		this.controlView.updateTemps(value);
	}
});

// work around a stupid iOS6 bug where ajax requests get cached and only work once, as described at
// http://stackoverflow.com/questions/12506897/is-safari-on-ios-6-caching-ajax-results
$.ajaxSetup({
    type: 'POST',
    headers: { "cache-control": "no-cache" }
});

// send the current UI API key with any request
$.ajaxSetup({
    headers: {"X-Api-Key": UI_API_KEY}
});

var app = new AstroBoxApp();