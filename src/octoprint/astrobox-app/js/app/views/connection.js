var ConnectionView = Backbone.View.extend({
	el: '#connection-view',
	connect: function() {
		this.$el.addClass('connecting').removeClass(['failed', 'connected']);
		var self = this;

        /*$.ajax({
            url: API_BASEURL + "connection",
            method: "GET",
            dataType: "json",
            success: function(response) {
            	self.$el.addClass('connected').removeClass('connecting');
            	console.log(response);
            }
        })*/

        var data = {
            "command": "connect",
            "port": '/dev/tty.usbmodemfd121',
            "baudrate": 250000,
            "autoconnect": true
        };

        $.ajax({
            url: API_BASEURL + "connection",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data),
            success: function(response) {
            	self.$el.addClass('connected').removeClass('connecting');
            },
            error: function() {
            	self.$el.addClass('failed').removeClass('connecting');
            }
        });
	},
	disconnect: function() {
	    $.ajax({
	        url: API_BASEURL + "connection",
	        type: "POST",
	        dataType: "json",
	        contentType: "application/json; charset=UTF-8",
	        data: JSON.stringify({"command": "disconnect"}),
	        success: function(response) {
	        	self.$el.removeClass('connected');
	        }
	    });	
	}
});