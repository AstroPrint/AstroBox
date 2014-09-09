/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
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

		this.eventManager = Backbone.Events;

		this.socketData.connectionView = this.connectionView;
		this.connectionView.socketData = this.socketData;
		this.socketData.connect();
		this.listenTo(this.socketData, 'change:printing', this.reportPrintingChange );
	},
	turnOffClicked: function()
	{
		this.turnOffModal.open();
	},
	reportPrintingChange: function(s, value) {
		if (value) {
			this.showPrinting();
		} else {
			this.$el.find('.tab-bar .left-small').show();
			this.router.navigate("", {replace: true, trigger: true});
		}
	},
	showPrinting: function() {
		this.$el.find('.tab-bar .left-small').hide();
		this.router.navigate("printing", {replace: true, trigger: true});
	}
});

app = new AstroBoxApp();

Backbone.history.start();