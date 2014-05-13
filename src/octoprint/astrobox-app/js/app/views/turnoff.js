var TurnoffConfirmationModal = Backbone.View.extend({
	el: '#turnoff-modal',
	parent: null,
	events: {
		'click button.alert': 'onConfirm'
	},
	onConfirm: function() {
		this.$el.foundation('reveal', 'close');
		this.parent.doTurnoff();
	}
});


var TurnoffView = Backbone.View.extend({
	el: '#turnoff-view',
	turnOffModal: new TurnoffConfirmationModal(),
	initialize: function() {
		this.turnOffModal.parent = this;
	},
	doTurnoff: function() {
		this.$el.removeClass('hide');
		$('#app').addClass('hide');

		var self = this;

		var data = {
            "action": "shutdown"
        }

        $.ajax({
            url: API_BASEURL + "system",
            type: "POST",
            data: data,
            success: function() {
				setTimeout(function() {
					self.$el.addClass('done');
					self.$el.find('.icon-off').removeClass('blink-animation');
				}, 5000);
            },
            error: function() {
            	self.$el.find('.icon-off').removeClass('blink-animation');
            }
        });
	}
});