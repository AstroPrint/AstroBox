/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

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
	appMenu: null,
	homeView: null,
	controlView: null,
	settingsView: null,
	connectionView: null,
	turnoffView: null,
	printingView: null,
	socketData: null,
	initialize: function() {
		this.socketData = new SocketData();
		this.appMenu = new AppMenu();
		this.homeView = new HomeView();
		this.controlView = new ControlView({app: this});
		this.settingsView = new SettingsView();
		this.connectionView = new ConnectionView();
		this.turnoffView = new TurnoffView();
		this.printingView = new PrintingView({app: this});

		this.socketData.connectionView = this.connectionView;
		this.socketData.homeView = this.homeView;
		this.connectionView.socketData = this.socketData;
		this.socketData.connect();
		this.listenTo(this.appMenu, 'view-changed', this.menuSelected );
		this.listenTo(this.socketData, 'change:printing', this.reportPrintingChange );
	},
	reportPrintingChange: function(s, value) {
		if (value) {
			this.showPrinting();
		} else {
			this.menuSelected('home');
			this.$el.find('#printing-view').addClass('hide');
			this.$el.find('.tab-bar .left-small').show();
		}
	},
	menuSelected: function(view) {
		var currentView = this.$el.find('#'+this.appMenu.selected+'-view');
		var targetView = this.$el.find('#'+view+'-view');

		currentView.addClass('hide');
		targetView.removeClass('hide');

		if (view == 'control') {
			this.controlView.tempView.resetBars();
		}
	},
	showPrinting: function() {
		this.menuSelected('printing');
		this.$el.find('.tab-bar .left-small').hide();
		this.printingView.show();
	}
});

app = new AstroBoxApp();