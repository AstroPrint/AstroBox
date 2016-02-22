/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

$.ajaxSetup({
    type: 'POST',
    cache: false,
    headers: {
    	"X-Api-Key": UI_API_KEY
    }
});

var AppMenu = Backbone.View.extend({
	el: '#main-menu',
	turnOffModal: null,
	events: {
		'click li.logout': 'logoutClicked'
	},
	logoutClicked: function(e) {
		e.preventDefault();
		var el = $(e.currentTarget);
		var spinIcon = el.find('.icon-rocket-spinner');

		spinIcon.removeClass('hide');
        $.ajax({
            url: API_BASEURL + "astroprint",
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
	eventManager: null,
	appMenu: null,
	socketData: null,
	utils: null,
	router: null,
	connectionView: null,
	turnOffModal: null,
	printerProfile: null,
	events: {
		'click button.turn-off': 'turnOffClicked'
	},
	initialize: function() {
		this.socketData = new SocketData();
		this.appMenu = new AppMenu();
		this.utils = new Utils();
		this.router = new AppRouter();
		this.connectionView = new ConnectionView();
		this.turnOffModal = new TurnoffConfirmationModal();
		this.printerProfile = new PrinterProfile(initial_printer_profile);

		this.eventManager = Backbone.Events;

		this.socketData.connectionView = this.connectionView;
		this.connectionView.socketData = this.socketData;
		this.socketData.connect();
		this.listenTo(this.socketData, 'change:printing', this.reportPrintingChange );
		this.listenTo(this.socketData, 'change:online', this.onlineStatusChange );
	},
	turnOffClicked: function()
	{
		this.turnOffModal.open();
	},
	reportPrintingChange: function(s, value) {
		if (value) {
			this.$('.quick-nav').hide();
			this.showPrinting();
		} else {
			//clear current printing data
			this.socketData.set({
				printing_progress: null,
				print_capture: null
			}, {silent: true});
			this.$('.tab-bar .left-small').show();
			this.$('.quick-nav').show();
			this.router.navigate("control", {replace: true, trigger: true});
		}
	},
	selectQuickNav: function(tab)
	{
		var nav = this.$('.quick-nav');
		nav.find('li.active').removeClass('active');
    if (tab) {
		  nav.find('li.'+tab).addClass('active');
    }
	},
	onlineStatusChange: function(s, value)
	{
		if (value) {
			this.$('#app').addClass('online').removeClass('offline');
		} else {
			this.$('#app').addClass('offline').removeClass('online');
		}
	},
	showPrinting: function() {
		this.$el.find('.tab-bar .left-small').hide();
		this.router.navigate("printing", {replace: true, trigger: true});
	}
});

app = new AstroBoxApp();

$(document)
  .foundation({
    abide : {
      patterns: {
        hostname: /^[A-Za-z0-9\-]+$/
      }
    }
  });

//This code is for astroprint.com communication with astrobox webUI window
//It doesn't really work now, so we comment it out for now
/*function receiveMessage(event)
{
	console.log(ASTROBOX_NAME);
  	event.source.postMessage(ASTROBOX_NAME, event.origin);
}

window.addEventListener("message", receiveMessage, false);*/

Backbone.history.start();
