var AppMenu = Backbone.View.extend({
	el: '#main-menu',
	selected: 'home',
	events: {
		'click li.view': 'menuItemClicked',
		'click li.logout': 'logoutClicked'
	},
	menuItemClicked: function(e) {
		e.preventDefault();
		var el = $(e.currentTarget);
		var view = el.attr('data-view');

		if (view != this.selected) {
			this.trigger('view-changed', view);
			this.selected = view;
		}
	},
	logoutClicked: function(e) {
		e.preventDefault();
		var el = $(e.currentTarget);
		var spinIcon = el.find('.icon-spin1');

		spinIcon.removeClass('hide');
        $.ajax({
            url: API_BASEURL + "cloud-slicer",
            type: "DELETE",
            success: function() { 
            	location.reload();
            },
            complete: function() {
				spinIcon.addClass('hide');
            }
        });
	}
});


var AstroBoxApp = Backbone.View.extend({
	el: 'body',
	appMenu: new AppMenu(),
	homeView: new HomeView(),
	controlView: new ControlView(),
	settingsView: new SettingsView(),
	connectionView: new ConnectionView(),
	turnoffView: new TurnoffView(),
	socketData: new SocketData(),
	initialize: function() {
		this.socketData.connectionView = this.connectionView;
		this.connectionView.socketData = this.socketData;
		this.socketData.connect();
		this.listenTo(this.socketData, 'change:temps', this.reportTempChange );
		this.listenTo(this.appMenu, 'view-changed', this.menuSelected );
	},
	reportTempChange: function(s, value) {
		if (this.appMenu.selected == 'control') {
			this.controlView.updateTemps(value);
		}
	},
	menuSelected: function(view) {
		var currentView = this.$el.find('#'+this.appMenu.selected+'-view');
		var targetView = this.$el.find('#'+view+'-view');

		currentView.addClass('hide');
		targetView.removeClass('hide');

		if (view == 'control') {
			this.controlView.tempView.nozzleTempBar.onResize();
			this.controlView.tempView.bedTempBar.onResize();
		}
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